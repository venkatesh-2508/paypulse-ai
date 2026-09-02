"""
PayPulse AI — Incidents API
Full incident lifecycle endpoints.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import text, select

from backend.database import get_db, sync_engine
from backend.models import (
    Incident, Recommendation, ActionResult, AuditLog,
    IncidentStatus, IncidentSeverity, ApprovalStatus
)
from backend.services.incident_service import IncidentService
from backend.investigation.investigation_engine import InvestigationEngine

router = APIRouter(tags=["incidents"])
incident_service = IncidentService()
investigation_engine = InvestigationEngine()


class ApproveRequest(BaseModel):
    approved_by: str = "merchant@demomart.com"


class RejectRequest(BaseModel):
    rejected_by: str = "merchant@demomart.com"
    reason: str


class ChatRequest(BaseModel):
    question: str
    incident_id: str


def _to_iso(val):
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


def _compute_duration_minutes(start_time, resolved_at=None) -> float:
    if not start_time:
        return 0.0
    try:
        if isinstance(start_time, str):
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        else:
            start_dt = start_time

        if resolved_at:
            if isinstance(resolved_at, str):
                end_dt = datetime.fromisoformat(resolved_at.replace("Z", "+00:00"))
            else:
                end_dt = resolved_at
        else:
            end_dt = datetime.now(timezone.utc)

        if start_dt.tzinfo is None and end_dt.tzinfo is not None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        elif start_dt.tzinfo is not None and end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)

        return max(0.0, (end_dt - start_dt).total_seconds() / 60.0)
    except Exception:
        return 0.0


@router.get("/incidents")
async def list_incidents(
    severity: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List incidents with optional filters."""
    query = """
        SELECT i.*, m.name as merchant_name
        FROM incidents i
        JOIN merchants m ON i.merchant_id = m.id
        WHERE 1=1
    """
    params = {"limit": limit, "offset": offset}

    if severity:
        query += " AND i.severity = :severity"
        params["severity"] = severity
    if status:
        query += " AND i.status = :status"
        params["status"] = status

    query += " ORDER BY i.created_at DESC LIMIT :limit OFFSET :offset"

    result = await db.execute(text(query), params)
    rows = result.fetchall()

    return {
        "incidents": [
            {
                "id": str(r.id),
                "merchant_name": r.merchant_name,
                "severity": r.severity,
                "status": r.status,
                "title": r.title,
                "start_time": _to_iso(r.start_time),
                "detected_at": _to_iso(r.detected_at),
                "resolved_at": _to_iso(r.resolved_at),
                "current_success_rate": r.current_success_rate,
                "baseline_success_rate": r.baseline_success_rate,
                "affected_transaction_count": r.affected_transaction_count,
                "estimated_exposure": float(r.estimated_exposure or 0),
                "duration_minutes": round(_compute_duration_minutes(r.start_time, r.resolved_at), 1),
            }
            for r in rows
        ],
        "total": len(rows),
    }


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str, db: AsyncSession = Depends(get_db)):
    """Get full incident detail."""
    result = await db.execute(
        text("""
            SELECT i.*, m.name as merchant_name
            FROM incidents i JOIN merchants m ON i.merchant_id = m.id
            WHERE i.id = :id
        """),
        {"id": incident_id}
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Get signals
    signals_result = await db.execute(
        text("SELECT * FROM incident_signals WHERE incident_id = :id ORDER BY deviation_pct DESC"),
        {"id": incident_id}
    )
    signals = [dict(r._mapping) for r in signals_result.fetchall()]

    # Get hypotheses
    hyp_result = await db.execute(
        text("SELECT * FROM incident_hypotheses WHERE incident_id = :id ORDER BY confidence DESC"),
        {"id": incident_id}
    )
    hypotheses = [dict(r._mapping) for r in hyp_result.fetchall()]

    # Get recommendation
    rec_result = await db.execute(
        text("SELECT * FROM recommendations WHERE incident_id = :id ORDER BY created_at DESC LIMIT 1"),
        {"id": incident_id}
    )
    rec_row = rec_result.fetchone()
    recommendation = dict(rec_row._mapping) if rec_row else None

    # Get action result
    action_result = None
    if recommendation:
        ar_result = await db.execute(
            text("SELECT * FROM action_results WHERE recommendation_id = :id ORDER BY created_at DESC LIMIT 1"),
            {"id": str(recommendation["id"])}
        )
        ar_row = ar_result.fetchone()
        action_result = dict(ar_row._mapping) if ar_row else None

    return {
        "id": str(row.id),
        "merchant_id": str(row.merchant_id),
        "merchant_name": row.merchant_name,
        "severity": row.severity,
        "status": row.status,
        "title": row.title,
        "description": row.description,
        "start_time": _to_iso(row.start_time),
        "detected_at": _to_iso(row.detected_at),
        "resolved_at": _to_iso(row.resolved_at),
        "current_success_rate": row.current_success_rate,
        "baseline_success_rate": row.baseline_success_rate,
        "affected_transaction_count": row.affected_transaction_count,
        "estimated_exposure": float(row.estimated_exposure or 0),
        "duration_minutes": round(_compute_duration_minutes(row.start_time, row.resolved_at), 1),
        "investigation_report": row.investigation_report,
        "signals": signals,
        "hypotheses": hypotheses,
        "recommendation": recommendation,
        "action_result": action_result,
    }


@router.get("/incidents/{incident_id}/investigation")
async def get_investigation(incident_id: str, db: AsyncSession = Depends(get_db)):
    """Get the investigation report for an incident."""
    result = await db.execute(
        text("SELECT investigation_report, merchant_id, start_time FROM incidents WHERE id = :id"),
        {"id": incident_id}
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Incident not found")

    if not row.investigation_report:
        return {"status": "not_investigated", "message": "Investigation not yet run. POST /api/incidents/{id}/investigate to trigger."}

    return row.investigation_report


@router.get("/incidents/{incident_id}/timeline")
async def get_timeline(incident_id: str, db: AsyncSession = Depends(get_db)):
    """Get incident event timeline."""
    # Use sync engine for the service (it uses sync SQLAlchemy)
    from sqlalchemy.orm import Session as SyncSession
    with SyncSession(sync_engine) as session:
        timeline = incident_service.get_incident_timeline(session, incident_id)
    return {"timeline": timeline}


@router.get("/incidents/{incident_id}/impact")
async def get_impact(incident_id: str, db: AsyncSession = Depends(get_db)):
    """Get business impact estimation."""
    result = await db.execute(
        text("SELECT * FROM incidents WHERE id = :id"), {"id": incident_id}
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Incident not found")

    try:
        start = row.start_time
    except Exception:
        start = datetime.now(timezone.utc) - timedelta(hours=1)

    end = datetime.now(timezone.utc)

    impact_sql = text("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) AS failures,
            SUM(CASE WHEN status = 'FAILED' THEN CAST(amount AS FLOAT) ELSE 0 END) AS failed_value,
            AVG(CAST(amount AS FLOAT)) AS avg_amount,
            COUNT(DISTINCT CASE WHEN status = 'FAILED' THEN customer_id END) AS affected_customers
        FROM transactions
        WHERE merchant_id = :merchant_id AND created_at BETWEEN :start AND :end
    """)
    impact_result = await db.execute(impact_sql, {
        "merchant_id": str(row.merchant_id), "start": start, "end": end
    })
    imp_row = impact_result.fetchone()

    baseline_rate = row.baseline_success_rate or 0.93
    total = int(imp_row.total or 0)
    failures = int(imp_row.failures or 0)
    expected_failures = total * (1 - baseline_rate)
    incremental = max(0, failures - expected_failures)
    avg_amount = float(imp_row.avg_amount or 0)
    estimated_exposure = incremental * avg_amount

    return {
        "incident_id": incident_id,
        "total_transactions_in_window": total,
        "actual_failures": failures,
        "expected_failures": round(expected_failures, 1),
        "incremental_failures": round(incremental, 1),
        "failed_transaction_value": float(imp_row.failed_value or 0),
        "estimated_exposure_inr": round(estimated_exposure, 2),
        "avg_transaction_value": round(avg_amount, 2),
        "affected_customers": int(imp_row.affected_customers or 0),
        "formula": "estimated_exposure = incremental_failures × avg_transaction_value",
        "note": "Estimate only. Actual impact depends on retry success and user behavior.",
        "confidence": "MEDIUM",
    }


@router.get("/incidents/{incident_id}/recommendation")
async def get_recommendation(incident_id: str, db: AsyncSession = Depends(get_db)):
    """Get the current recommendation for an incident."""
    result = await db.execute(
        text("SELECT * FROM recommendations WHERE incident_id = :id ORDER BY created_at DESC LIMIT 1"),
        {"id": incident_id}
    )
    row = result.fetchone()
    if not row:
        return {"message": "No recommendation yet. Run investigation first."}
    return dict(row._mapping)


@router.post("/incidents/{incident_id}/investigate")
async def trigger_investigation(
    incident_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger AI investigation for an incident."""
    result = await db.execute(
        text("SELECT * FROM incidents WHERE id = :id"), {"id": incident_id}
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Update status to INVESTIGATING
    await db.execute(
        text("UPDATE incidents SET status = 'INVESTIGATING', updated_at = :now WHERE id = :id"),
        {"id": incident_id, "now": datetime.now(timezone.utc)}
    )
    await db.commit()

    # Extract scalar values while the session is still open to avoid DetachedInstanceError
    merchant_id_val = str(row.merchant_id)
    start_time_val = row.start_time

    # Run investigation in background
    background_tasks.add_task(
        _run_investigation_background,
        incident_id=incident_id,
        merchant_id=merchant_id_val,
        start_time=start_time_val,
    )

    return {
        "status": "investigating",
        "message": "AI investigation started. Poll GET /api/incidents/{id}/investigation for results.",
        "incident_id": incident_id,
    }


async def _run_investigation_background(
    incident_id: str, merchant_id: str, start_time: datetime
):
    """Background task to run AI investigation."""
    import asyncio
    from sqlalchemy.orm import Session as SyncSession

    # Run in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _sync_investigate, incident_id, merchant_id, start_time)


def _sync_investigate(incident_id: str, merchant_id: str, start_time: datetime):
    """Synchronous investigation runner (runs in thread pool)."""
    from sqlalchemy.orm import Session as SyncSession
    from backend.agents.investigation_agent import PayPulseAgent, ToolExecutor
    from backend.investigation.investigation_engine import InvestigationEngine

    inv_engine = InvestigationEngine()

    with SyncSession(sync_engine) as session:
        tool_executor = ToolExecutor(
            db_session=session,
            investigation_engine=inv_engine,
            impact_calculator=None,
        )
        agent = PayPulseAgent(tool_executor=tool_executor)
        report = agent.investigate(incident_id)

        # Store results
        incident_service.update_investigation(session, incident_id, report)
        session.commit()
        print(f"[investigation] Completed for incident {incident_id}")


@router.post("/incidents/{incident_id}/approve")
async def approve_recommendation(
    incident_id: str,
    body: ApproveRequest,
    db: AsyncSession = Depends(get_db),
):
    """Approve the pending recommendation."""
    rec_result = await db.execute(
        text("SELECT id FROM recommendations WHERE incident_id = :id AND approval_status = 'PENDING' ORDER BY created_at DESC LIMIT 1"),
        {"id": incident_id}
    )
    rec_row = rec_result.fetchone()
    if not rec_row:
        raise HTTPException(status_code=404, detail="No pending recommendation found")

    from sqlalchemy.orm import Session as SyncSession
    with SyncSession(sync_engine) as session:
        incident_service.approve_recommendation(session, str(rec_row.id), body.approved_by)
        session.commit()

    return {"status": "approved", "recommendation_id": str(rec_row.id)}


@router.post("/incidents/{incident_id}/reject")
async def reject_recommendation(
    incident_id: str,
    body: RejectRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reject the pending recommendation."""
    rec_result = await db.execute(
        text("SELECT id FROM recommendations WHERE incident_id = :id ORDER BY created_at DESC LIMIT 1"),
        {"id": incident_id}
    )
    rec_row = rec_result.fetchone()
    if not rec_row:
        raise HTTPException(status_code=404, detail="No recommendation found")

    from sqlalchemy.orm import Session as SyncSession
    with SyncSession(sync_engine) as session:
        incident_service.reject_recommendation(session, str(rec_row.id), body.rejected_by, body.reason)
        session.commit()

    return {"status": "rejected", "recommendation_id": str(rec_row.id)}


@router.post("/incidents/{incident_id}/execute")
async def execute_action(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Execute the approved action."""
    rec_result = await db.execute(
        text("SELECT id FROM recommendations WHERE incident_id = :id AND approval_status = 'APPROVED' ORDER BY created_at DESC LIMIT 1"),
        {"id": incident_id}
    )
    rec_row = rec_result.fetchone()
    if not rec_row:
        raise HTTPException(status_code=404, detail="No approved recommendation found. Approve first.")

    from sqlalchemy.orm import Session as SyncSession
    with SyncSession(sync_engine) as session:
        result = incident_service.execute_action(session, str(rec_row.id))
        session.commit()
        return {
            "status": "executed",
            "verification_result": result.verification_result.value if result.verification_result else None,
            "success_rate_before": result.success_rate_before,
            "success_rate_after": result.success_rate_after,
            "absolute_improvement": result.absolute_improvement,
            "pct_improvement": result.pct_improvement,
        }


@router.get("/incidents/{incident_id}/verification")
async def get_verification(incident_id: str, db: AsyncSession = Depends(get_db)):
    """Get post-action verification results."""
    result = await db.execute(
        text("""
            SELECT ar.* FROM action_results ar
            JOIN recommendations rec ON ar.recommendation_id = rec.id
            WHERE rec.incident_id = :id
            ORDER BY ar.created_at DESC LIMIT 1
        """),
        {"id": incident_id}
    )
    row = result.fetchone()
    if not row:
        return {"message": "No action result yet"}
    return dict(row._mapping)


@router.post("/incidents/{incident_id}/chat")
async def chat_with_investigator(
    incident_id: str,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    AI Investigator chat — answers questions grounded in incident data.
    Questions must be about the specific incident.
    """
    # Get investigation report
    result = await db.execute(
        text("SELECT investigation_report, current_success_rate, baseline_success_rate, severity, title FROM incidents WHERE id = :id"),
        {"id": incident_id}
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Incident not found")

    report = row.investigation_report or {}

    # Answer questions using structured data (no LLM hallucination risk)
    question_lower = body.question.lower()
    answer = _answer_from_data(question_lower, row, report)

    return {
        "question": body.question,
        "answer": answer,
        "grounded_in": "incident investigation data",
        "incident_id": incident_id,
    }


def _answer_from_data(question: str, incident_row, report: dict) -> str:
    """Answer investigator questions from structured data."""
    curr = incident_row.current_success_rate or 0
    base = incident_row.baseline_success_rate or 0.93
    degradation = (base - curr) * 100

    if any(w in question for w in ["why", "cause", "reason", "happened"]):
        causes = report.get("candidate_causes", [])
        if causes:
            primary = causes[0]
            return (
                f"**Primary hypothesis ({primary.get('confidence',0)*100:.0f}% confidence):** "
                f"{primary.get('hypothesis', 'Unknown')}.\n\n"
                f"**Evidence:** {', '.join(primary.get('supporting_evidence', []))}\n\n"
                f"{report.get('reasoning_summary', '')}"
            )
        return f"Payment success rate dropped {degradation:.1f}pp from baseline. Investigation report not yet available."

    if any(w in question for w in ["segment", "affected", "which", "where"]):
        segments = report.get("affected_segments", [])
        if segments:
            return "**Most affected segments:**\n" + "\n".join(f"- {s}" for s in segments[:5])
        return "Run investigation to see affected segments."

    if any(w in question for w in ["evidence", "support", "proof", "data"]):
        evidence = report.get("key_evidence", [])
        if evidence:
            return "**Key evidence from investigation:**\n" + "\n".join(f"- {e}" for e in evidence)
        return "No evidence collected yet."

    if any(w in question for w in ["impact", "revenue", "exposure", "loss", "money", "value", "₹"]):
        impact = report.get("business_impact", {})
        if impact:
            return (
                f"**Estimated Business Impact:**\n"
                f"- Affected transactions: {impact.get('affected_transactions', 0):,}\n"
                f"- Estimated exposure: ₹{impact.get('estimated_exposure_inr', 0):,.0f}\n"
                f"- Customers affected: {impact.get('customers_affected', 0):,}\n"
                f"- Severity: {impact.get('severity', 'UNKNOWN')}\n\n"
                f"*Note: This is an estimate based on incremental_failures × avg_transaction_value.*"
            )
        return f"Estimated exposure: ₹{float(incident_row.estimated_exposure or 0):,.0f}"

    if any(w in question for w in ["intervention", "action", "work", "improve", "fix", "better"]):
        ar = report.get("action_result", {})
        what_changed = report.get("what_changed", "")
        return (
            f"**What changed:** {report.get('what_changed', 'See incident details for timeline.')}\n\n"
            f"**Recommended action:** {report.get('recommended_action', 'Not yet determined')}\n\n"
            f"Check the Verification tab to see before/after metrics after action execution."
        )

    if any(w in question for w in ["success rate", "failure rate", "how bad", "performance"]):
        return (
            f"**Current success rate:** {curr*100:.1f}%\n"
            f"**Baseline success rate:** {base*100:.1f}%\n"
            f"**Degradation:** {degradation:.1f} percentage points\n"
            f"**Severity:** {incident_row.severity}"
        )

    if any(w in question for w in ["start", "when", "begin", "time"]):
        return (
            f"**Incident started:** {report.get('when_it_started', 'Unknown')}\n"
            f"**What changed:** {report.get('what_changed', 'See investigation report.')}"
        )

    # Default: return summary
    return (
        f"{report.get('incident_summary', incident_row.title or 'Incident under investigation.')}\n\n"
        f"**Next steps:** {', '.join(report.get('next_steps', ['Run investigation']))}"
    )
