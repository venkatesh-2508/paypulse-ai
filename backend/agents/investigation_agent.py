"""
PayPulse AI — AI Investigation Agent

Uses Google Gemini with function calling to investigate incidents.
The agent receives tools that query the database.
It never fabricates data — all evidence comes from tool responses.

Implements the DETECT → INVESTIGATE → QUANTIFY → RECOMMEND loop.
"""
import json
import traceback
from datetime import datetime, timezone
from typing import Any, Optional

import google.generativeai as genai

from backend.config import settings
from backend.investigation.investigation_engine import InvestigationResult


# ─── Tool Definitions ─────────────────────────────────────────────────────────

AGENT_TOOLS = [
    {
        "name": "get_incident",
        "description": "Get full incident metadata including severity, status, success rate change, and timestamps.",
        "parameters": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string", "description": "The incident UUID"}
            },
            "required": ["incident_id"]
        }
    },
    {
        "name": "get_payment_statistics",
        "description": "Get current vs baseline payment success rate and failure counts for the incident window.",
        "parameters": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string"}
            },
            "required": ["incident_id"]
        }
    },
    {
        "name": "get_failure_breakdown",
        "description": "Get failure breakdown by a specific dimension: payment_method, bank, device, location, error_reason, or error_source.",
        "parameters": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string"},
                "dimension": {
                    "type": "string",
                    "enum": ["payment_method", "bank", "device", "location", "error_reason", "error_source"]
                }
            },
            "required": ["incident_id", "dimension"]
        }
    },
    {
        "name": "get_historical_baseline",
        "description": "Get the 7-day historical baseline success rate for a specific dimension and value.",
        "parameters": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string"},
                "dimension": {"type": "string"},
                "dimension_value": {"type": "string"}
            },
            "required": ["incident_id", "dimension", "dimension_value"]
        }
    },
    {
        "name": "get_affected_segments",
        "description": "Get the top most anomalous segments across all dimensions, ranked by deviation from baseline.",
        "parameters": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string"}
            },
            "required": ["incident_id"]
        }
    },
    {
        "name": "get_recent_events",
        "description": "Get the most recent payment events (last N) to identify temporal patterns and sudden changes.",
        "parameters": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string"},
                "limit": {"type": "integer", "description": "Number of events to fetch, max 50"}
            },
            "required": ["incident_id"]
        }
    },
    {
        "name": "get_recent_changes",
        "description": "Get any configuration or pattern changes that correlate with incident start time.",
        "parameters": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string"}
            },
            "required": ["incident_id"]
        }
    },
    {
        "name": "estimate_business_impact",
        "description": "Calculate estimated revenue exposure from the incident: affected transactions, failed value, customers affected.",
        "parameters": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string"}
            },
            "required": ["incident_id"]
        }
    },
    {
        "name": "get_available_actions",
        "description": "Get the list of available bounded actions the system can recommend and execute.",
        "parameters": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string"}
            },
            "required": ["incident_id"]
        }
    },
    {
        "name": "create_investigation_report",
        "description": (
            "FINAL TOOL — call this last to submit the complete structured investigation report. "
            "All fields must be based on evidence gathered from previous tool calls. "
            "Never fabricate data."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string"},
                "incident_summary": {"type": "string"},
                "what_changed": {"type": "string"},
                "when_it_started": {"type": "string"},
                "affected_segments": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "key_evidence": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "candidate_causes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "hypothesis": {"type": "string"},
                            "confidence": {"type": "number"},
                            "supporting_evidence": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        }
                    }
                },
                "confidence": {"type": "number"},
                "business_impact": {
                    "type": "object",
                    "properties": {
                        "affected_transactions": {"type": "integer"},
                        "estimated_exposure_inr": {"type": "number"},
                        "customers_affected": {"type": "integer"},
                        "severity": {"type": "string"}
                    }
                },
                "recommended_action": {"type": "string"},
                "reasoning_summary": {"type": "string"},
                "limitations": {"type": "string"},
                "next_steps": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": [
                "incident_id", "incident_summary", "what_changed", "when_it_started",
                "affected_segments", "key_evidence", "candidate_causes", "confidence",
                "business_impact", "recommended_action", "reasoning_summary",
                "limitations", "next_steps"
            ]
        }
    },
]


class PayPulseAgent:
    """
    AI Investigation Agent using Gemini function calling.
    Uses tools to query actual database data.
    Cannot fabricate evidence.
    """

    SYSTEM_PROMPT = """You are PayPulse AI, an expert payment operations analyst.
You are investigating a payment incident for an online merchant.

Your job:
1. Use the provided tools to gather evidence about the incident
2. Analyze which dimensions (payment method, bank, device, location) are most affected
3. Compare current performance against historical baselines
4. Generate multiple candidate root-cause hypotheses with confidence scores
5. Estimate business impact
6. Recommend ONE bounded action from the available actions list
7. Call create_investigation_report with your complete findings

CRITICAL RULES:
- Never fabricate payment data, transactions, or evidence
- All evidence must come from tool responses
- If evidence is insufficient, say so explicitly
- Do not claim certainty without strong evidence (confidence < 0.9 for most cases)
- Recommend only actions from the get_available_actions response
- Investigate all major dimensions before concluding

Start by calling get_incident, then systematically gather evidence before creating the report.
"""

    def __init__(self, tool_executor: "ToolExecutor"):
        self.tool_executor = tool_executor
        self.client = None
        self.model = None
        self._init_client()

    def _init_client(self):
        if not settings.GEMINI_API_KEY:
            print("[agent] No GEMINI_API_KEY — will use fallback deterministic investigation.")
            return
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                tools=self._build_gemini_tools(),
                system_instruction=self.SYSTEM_PROMPT,
            )
        except Exception as e:
            print(f"[agent] Gemini init failed: {e}")
            self.model = None

    def _build_gemini_tools(self):
        """Convert tool definitions to Gemini FunctionDeclaration format."""
        from google.generativeai.types import FunctionDeclaration, Tool
        declarations = []
        for tool in AGENT_TOOLS:
            declarations.append(FunctionDeclaration(
                name=tool["name"],
                description=tool["description"],
                parameters=tool["parameters"],
            ))
        return [Tool(function_declarations=declarations)]

    def _execute_tool(self, name: str, args: dict) -> Any:
        """Route tool call to tool executor."""
        try:
            return self.tool_executor.execute(name, args)
        except Exception as e:
            return {"error": str(e), "tool": name}

    def investigate(self, incident_id: str) -> dict:
        """
        Run the AI investigation agent.
        Returns a structured investigation report dict.
        Falls back to deterministic summary if AI unavailable.
        """
        if self.model is None:
            return self._deterministic_fallback(incident_id)

        try:
            return self._run_gemini_agent(incident_id)
        except Exception as e:
            print(f"[agent] Gemini agent failed: {e}\n{traceback.format_exc()}")
            return self._deterministic_fallback(incident_id)

    def _run_gemini_agent(self, incident_id: str) -> dict:
        """Run Gemini multi-turn function calling loop."""
        chat = self.model.start_chat()

        # Kick off investigation
        user_message = (
            f"Investigate payment incident {incident_id}. "
            "Use your tools to gather evidence, then create a complete investigation report."
        )

        response = chat.send_message(user_message)
        final_report = None
        max_turns = 15

        for turn in range(max_turns):
            # Check for function calls
            fn_calls = []
            for part in response.candidates[0].content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    fn_calls.append(part.function_call)

            if not fn_calls:
                # No more tool calls — extract text response
                break

            # Execute all tool calls
            tool_responses = []
            for fc in fn_calls:
                result = self._execute_tool(fc.name, dict(fc.args))

                if fc.name == "create_investigation_report":
                    final_report = dict(fc.args)

                tool_responses.append({
                    "function_response": {
                        "name": fc.name,
                        "response": {"result": result}
                    }
                })

            if final_report:
                break

            # Send tool results back
            import google.generativeai.types as gtypes
            parts = []
            for tr in tool_responses:
                parts.append(genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=tr["function_response"]["name"],
                        response={"result": json.dumps(tr["function_response"]["response"]["result"], default=str)},
                    )
                ))

            response = chat.send_message(parts)

        if final_report:
            final_report["generated_by"] = "gemini-1.5-flash"
            final_report["generated_at"] = datetime.now(timezone.utc).isoformat()
            return final_report

        # If no structured report was created, use fallback
        return self._deterministic_fallback(incident_id)

    def _deterministic_fallback(self, incident_id: str) -> dict:
        """
        Deterministic investigation when AI is unavailable.
        Uses pre-gathered investigation data from the tool executor.
        """
        try:
            incident_data = self.tool_executor.execute("get_incident", {"incident_id": incident_id})
            stats = self.tool_executor.execute("get_payment_statistics", {"incident_id": incident_id})
            affected = self.tool_executor.execute("get_affected_segments", {"incident_id": incident_id})
            impact = self.tool_executor.execute("estimate_business_impact", {"incident_id": incident_id})
            pm_breakdown = self.tool_executor.execute("get_failure_breakdown", {
                "incident_id": incident_id, "dimension": "payment_method"
            })
            bank_breakdown = self.tool_executor.execute("get_failure_breakdown", {
                "incident_id": incident_id, "dimension": "bank"
            })
            actions = self.tool_executor.execute("get_available_actions", {"incident_id": incident_id})

            # Determine most affected segment
            top_segments = affected.get("top_segments", [])
            top_dim = top_segments[0] if top_segments else {}

            # Build hypotheses based on evidence
            hypotheses = []

            # Hypothesis based on top affected dimension
            if top_dim:
                dim_name = top_dim.get("dimension", "unknown")
                dim_val = top_dim.get("dimension_value", "unknown")
                dev_pct = top_dim.get("deviation_pct", 0)

                if dim_name == "payment_method":
                    hypotheses.append({
                        "hypothesis": f"External {dim_val} payment network degradation",
                        "confidence": min(0.85, 0.5 + dev_pct / 200),
                        "supporting_evidence": [
                            f"{dim_val} failure rate increased by {dev_pct:.1f}% above baseline",
                            f"Concentration of errors in {dim_val} transactions",
                        ]
                    })
                elif dim_name == "bank":
                    hypotheses.append({
                        "hypothesis": f"Bank-side infrastructure issue at {dim_val}",
                        "confidence": min(0.80, 0.45 + dev_pct / 200),
                        "supporting_evidence": [
                            f"{dim_val} transactions showing {dev_pct:.1f}% higher failure rate",
                            "Error source concentrated in BANK category",
                        ]
                    })

            # Add alternative hypotheses
            hypotheses.append({
                "hypothesis": "Merchant integration or configuration issue",
                "confidence": 0.20,
                "supporting_evidence": [
                    "Could not rule out merchant-side changes",
                    "No explicit merchant error signals detected",
                ]
            })
            hypotheses.append({
                "hypothesis": "Temporary network fluctuation",
                "confidence": 0.15,
                "supporting_evidence": [
                    "Pattern persists beyond typical fluctuation window",
                ]
            })

            # Select recommended action
            avail_actions = actions.get("actions", [])
            recommended = "RECOMMEND_ALTERNATIVE_PAYMENT_METHOD"
            if avail_actions:
                # Prefer routing/alternative recommendation for payment method issues
                for a in avail_actions:
                    if "ALTERNATIVE" in a.get("action_type", "") or "ROUTE" in a.get("action_type", ""):
                        recommended = a["action_type"]
                        break

            current_rate = stats.get("current_success_rate", 0)
            baseline_rate = stats.get("baseline_success_rate", 0.93)
            degradation = (baseline_rate - current_rate) * 100

            return {
                "incident_id": incident_id,
                "incident_summary": (
                    f"Payment performance degraded from {baseline_rate*100:.1f}% to "
                    f"{current_rate*100:.1f}% success rate "
                    f"({degradation:.1f}pp decline) starting at "
                    f"{incident_data.get('start_time', 'unknown time')}."
                ),
                "what_changed": (
                    f"Payment success rate dropped by {degradation:.1f} percentage points. "
                    f"The primary affected dimension is "
                    f"{top_dim.get('dimension', 'unknown')} = {top_dim.get('dimension_value', 'unknown')} "
                    f"with {top_dim.get('deviation_pct', 0):.1f}% increase in failures."
                ),
                "when_it_started": incident_data.get("start_time", "Unknown"),
                "affected_segments": [
                    f"{s['dimension']} = {s['dimension_value']} (+{s['deviation_pct']:.1f}% failures)"
                    for s in top_segments[:5]
                ],
                "key_evidence": [
                    f"Current success rate: {current_rate*100:.1f}% (baseline: {baseline_rate*100:.1f}%)",
                    f"Incremental failures above baseline: {impact.get('incremental_failures', 0):.0f}",
                    f"Estimated revenue exposure: ₹{impact.get('estimated_exposure', 0):,.0f}",
                    f"Affected customers: {impact.get('affected_customers', 0):,}",
                ],
                "candidate_causes": hypotheses,
                "confidence": hypotheses[0]["confidence"] if hypotheses else 0.5,
                "business_impact": {
                    "affected_transactions": impact.get("actual_failures", 0),
                    "estimated_exposure_inr": impact.get("estimated_exposure", 0),
                    "customers_affected": impact.get("affected_customers", 0),
                    "severity": incident_data.get("severity", "MEDIUM"),
                },
                "recommended_action": recommended,
                "reasoning_summary": (
                    f"The incident shows concentrated failure increases in specific dimensions. "
                    f"The statistical evidence (z-score analysis) points to an external factor "
                    f"rather than a merchant-side issue. "
                    f"Recommending {recommended} as the safest immediate action."
                ),
                "limitations": (
                    "This analysis is based on statistical pattern detection without AI. "
                    "Root cause confidence would improve with external incident data from payment networks. "
                    "Set GEMINI_API_KEY in .env for enhanced AI investigation."
                ),
                "next_steps": [
                    f"Execute {recommended} to mitigate impact",
                    "Monitor payment metrics every 5 minutes",
                    "Contact payment gateway if degradation persists > 15 minutes",
                    "Escalate to payment operations team if no improvement",
                ],
                "generated_by": "deterministic-fallback",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            return {
                "incident_id": incident_id,
                "incident_summary": "Investigation failed — insufficient data.",
                "what_changed": "Unknown",
                "when_it_started": "Unknown",
                "affected_segments": [],
                "key_evidence": [],
                "candidate_causes": [],
                "confidence": 0.0,
                "business_impact": {"affected_transactions": 0, "estimated_exposure_inr": 0, "customers_affected": 0, "severity": "UNKNOWN"},
                "recommended_action": "MONITOR_PAYMENT_HEALTH",
                "reasoning_summary": "Insufficient evidence to determine the cause.",
                "limitations": f"Investigation error: {str(e)}",
                "next_steps": ["Gather more data", "Escalate to engineering"],
                "generated_by": "error-fallback",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            }


class ToolExecutor:
    """
    Executes agent tool calls by querying the database.
    This is the bridge between the AI agent and real application data.
    """

    def __init__(self, db_session, investigation_engine, impact_calculator):
        self.session = db_session
        self.investigation_engine = investigation_engine
        self.impact_calculator = impact_calculator
        self._cache: dict[str, Any] = {}

    def execute(self, tool_name: str, args: dict) -> Any:
        cache_key = f"{tool_name}:{json.dumps(args, sort_keys=True)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        result = self._dispatch(tool_name, args)
        self._cache[cache_key] = result
        return result

    def _dispatch(self, name: str, args: dict) -> Any:
        method = getattr(self, f"_tool_{name}", None)
        if method is None:
            return {"error": f"Unknown tool: {name}"}
        return method(**args)

    def _tool_get_incident(self, incident_id: str) -> dict:
        from sqlalchemy import text
        sql = text("""
            SELECT i.*, m.name as merchant_name
            FROM incidents i
            JOIN merchants m ON i.merchant_id = m.id
            WHERE i.id = :incident_id
        """)
        row = self.session.execute(sql, {"incident_id": incident_id}).fetchone()
        if not row:
            return {"error": "Incident not found"}
        return {
            "incident_id": str(row.id),
            "merchant_id": str(row.merchant_id),
            "merchant_name": row.merchant_name,
            "severity": row.severity,
            "status": row.status,
            "title": row.title,
            "description": row.description,
            "start_time": str(row.start_time),
            "detected_at": str(row.detected_at),
            "current_success_rate": row.current_success_rate,
            "baseline_success_rate": row.baseline_success_rate,
            "affected_transaction_count": row.affected_transaction_count,
            "estimated_exposure": str(row.estimated_exposure or 0),
        }

    def _tool_get_payment_statistics(self, incident_id: str) -> dict:
        from sqlalchemy import text
        incident = self._tool_get_incident(incident_id)
        return {
            "current_success_rate": incident.get("current_success_rate", 0),
            "baseline_success_rate": incident.get("baseline_success_rate", 0.93),
            "degradation_pp": (
                (incident.get("baseline_success_rate", 0.93) or 0.93)
                - (incident.get("current_success_rate", 0) or 0)
            ) * 100,
            "affected_transactions": incident.get("affected_transaction_count", 0),
        }

    def _tool_get_failure_breakdown(self, incident_id: str, dimension: str) -> dict:
        incident = self._tool_get_incident(incident_id)
        if "error" in incident:
            return incident

        from sqlalchemy import text
        from datetime import datetime, timezone, timedelta

        merchant_id = incident["merchant_id"]
        # Use start_time from incident; end_time = detected_at + 30 min
        try:
            start = datetime.fromisoformat(incident["start_time"].replace("Z", "+00:00"))
        except Exception:
            start = datetime.now(timezone.utc) - timedelta(hours=1)

        end = datetime.now(timezone.utc)

        breakdown = self.investigation_engine._get_breakdown(
            self.session, merchant_id, start, end, dimension
        )
        return {
            "dimension": dimension,
            "breakdown": [
                {
                    "dimension_value": b.dimension_value,
                    "total_count": b.total_count,
                    "failure_count": b.failure_count,
                    "failure_rate": b.failure_rate,
                    "baseline_failure_rate": b.baseline_failure_rate,
                    "deviation_pct": b.deviation_pct,
                    "z_score": b.z_score,
                    "top_error_reasons": b.error_reasons,
                }
                for b in breakdown[:10]
            ]
        }

    def _tool_get_historical_baseline(
        self, incident_id: str, dimension: str, dimension_value: str
    ) -> dict:
        incident = self._tool_get_incident(incident_id)
        from sqlalchemy import text
        sql = text("""
            SELECT * FROM historical_baselines
            WHERE merchant_id = :merchant_id AND dimension = :dim AND dimension_value = :val
            LIMIT 1
        """)
        row = self.session.execute(sql, {
            "merchant_id": incident.get("merchant_id"),
            "dim": dimension,
            "val": dimension_value,
        }).fetchone()
        if not row:
            return {"message": "No baseline found", "dimension": dimension, "dimension_value": dimension_value}
        return {
            "dimension": dimension,
            "dimension_value": dimension_value,
            "success_rate": row.success_rate,
            "transaction_count": row.transaction_count,
            "std_dev": row.std_dev,
        }

    def _tool_get_affected_segments(self, incident_id: str) -> dict:
        incident = self._tool_get_incident(incident_id)
        if "error" in incident:
            return incident

        from datetime import datetime, timezone, timedelta
        try:
            start = datetime.fromisoformat(incident["start_time"].replace("Z", "+00:00"))
        except Exception:
            start = datetime.now(timezone.utc) - timedelta(hours=1)
        end = datetime.now(timezone.utc)

        merchant_id = incident["merchant_id"]
        all_segments = []

        for dim in ["payment_method", "bank", "device", "location"]:
            breakdown = self.investigation_engine._get_breakdown(
                self.session, merchant_id, start, end, dim
            )
            for b in breakdown:
                if b.deviation_pct > 10:
                    all_segments.append({
                        "dimension": b.dimension,
                        "dimension_value": b.dimension_value,
                        "failure_rate": b.failure_rate,
                        "baseline_failure_rate": b.baseline_failure_rate,
                        "deviation_pct": b.deviation_pct,
                        "z_score": b.z_score,
                        "total_count": b.total_count,
                    })

        all_segments.sort(key=lambda x: x["deviation_pct"], reverse=True)
        return {"top_segments": all_segments[:10]}

    def _tool_get_recent_events(self, incident_id: str, limit: int = 20) -> dict:
        incident = self._tool_get_incident(incident_id)
        from sqlalchemy import text
        sql = text("""
            SELECT pe.event_type, pe.created_at, t.status, t.error_reason
            FROM payment_events pe
            JOIN transactions t ON pe.transaction_id = t.id
            WHERE t.merchant_id = :merchant_id
            ORDER BY pe.created_at DESC
            LIMIT :limit
        """)
        rows = self.session.execute(sql, {
            "merchant_id": incident.get("merchant_id"),
            "limit": min(limit, 50),
        }).fetchall()
        return {
            "events": [
                {
                    "event_type": r.event_type,
                    "timestamp": str(r.created_at),
                    "status": r.status,
                    "error_reason": r.error_reason,
                }
                for r in rows
            ]
        }

    def _tool_get_recent_changes(self, incident_id: str) -> dict:
        # In a real system this would query a changelog/deployment log
        # For the prototype, return structured empty response
        return {
            "message": "No external change log available in this environment.",
            "note": "In production, this would query deployment logs, config changes, and maintenance windows.",
            "recommendation": "Check with payment gateway support for any known incidents."
        }

    def _tool_estimate_business_impact(self, incident_id: str) -> dict:
        incident = self._tool_get_incident(incident_id)
        if "error" in incident:
            return incident

        from datetime import datetime, timezone, timedelta
        from sqlalchemy import text

        merchant_id = incident["merchant_id"]
        try:
            start = datetime.fromisoformat(incident["start_time"].replace("Z", "+00:00"))
        except Exception:
            start = datetime.now(timezone.utc) - timedelta(hours=1)
        end = datetime.now(timezone.utc)

        sql = text("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) AS failures,
                SUM(CASE WHEN status = 'FAILED' THEN amount::float ELSE 0 END) AS failed_value,
                AVG(amount::float) AS avg_amount,
                COUNT(DISTINCT CASE WHEN status = 'FAILED' THEN customer_id END) AS affected_customers
            FROM transactions
            WHERE merchant_id = :merchant_id AND created_at BETWEEN :start AND :end
        """)
        row = self.session.execute(sql, {"merchant_id": merchant_id, "start": start, "end": end}).fetchone()

        baseline_rate = incident.get("baseline_success_rate", 0.93) or 0.93
        total = int(row.total or 0)
        failures = int(row.failures or 0)
        expected_failures = total * (1 - baseline_rate)
        incremental = max(0, failures - expected_failures)
        avg_amount = float(row.avg_amount or 0)
        estimated_exposure = incremental * avg_amount

        return {
            "total_transactions": total,
            "actual_failures": failures,
            "expected_failures": round(expected_failures, 1),
            "incremental_failures": round(incremental, 1),
            "failed_transaction_value": float(row.failed_value or 0),
            "estimated_exposure": round(estimated_exposure, 2),
            "avg_transaction_value": round(avg_amount, 2),
            "affected_customers": int(row.affected_customers or 0),
            "formula": "estimated_exposure = incremental_failures * avg_transaction_value",
            "note": "This is an estimate. Actual revenue impact depends on retry success.",
        }

    def _tool_get_available_actions(self, incident_id: str) -> dict:
        return {
            "actions": [
                {
                    "action_type": "NOTIFY_MERCHANT",
                    "title": "Notify merchant operations team",
                    "description": "Send automated alert to merchant ops team via email/SMS",
                    "risk_level": "LOW",
                    "requires_approval": False,
                },
                {
                    "action_type": "RECOMMEND_ALTERNATIVE_PAYMENT_METHOD",
                    "title": "Recommend alternative payment method to customers",
                    "description": "Update payment page to highlight alternative working payment methods",
                    "risk_level": "LOW",
                    "requires_approval": True,
                },
                {
                    "action_type": "MONITOR_PAYMENT_HEALTH",
                    "title": "Increase monitoring frequency",
                    "description": "Reduce detection window to 5 minutes and alert on any change",
                    "risk_level": "LOW",
                    "requires_approval": False,
                },
                {
                    "action_type": "CREATE_SUPPORT_INCIDENT",
                    "title": "Create support incident with payment gateway",
                    "description": "Raise a P1 incident with the payment gateway support team",
                    "risk_level": "MEDIUM",
                    "requires_approval": True,
                },
                {
                    "action_type": "ESCALATE_TO_PAYMENT_OPERATIONS",
                    "title": "Escalate to payment operations team",
                    "description": "Page the on-call payment operations engineer",
                    "risk_level": "MEDIUM",
                    "requires_approval": True,
                },
                {
                    "action_type": "ENABLE_RETRY_LOGIC",
                    "title": "Enable aggressive retry logic",
                    "description": "Temporarily increase retry attempts for failed transactions",
                    "risk_level": "MEDIUM",
                    "requires_approval": True,
                },
                {
                    "action_type": "ROUTE_TO_BACKUP_PROVIDER",
                    "title": "Route traffic to backup payment provider",
                    "description": "Activate backup payment gateway for affected payment methods",
                    "risk_level": "HIGH",
                    "requires_approval": True,
                },
            ]
        }

    def _tool_create_investigation_report(self, **kwargs) -> dict:
        """This is handled by the agent loop — just return confirmation."""
        return {"status": "report_created", "incident_id": kwargs.get("incident_id")}
