"""
PayPulse AI — Investigation Engine

Performs multi-dimensional analysis of a payment incident.
Identifies most-affected segments, computes deviations from baseline,
finds temporal patterns, and gathers structured evidence.
This is a DETERMINISTIC analysis — not LLM-driven.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.models import IncidentSeverity


@dataclass
class DimensionBreakdown:
    dimension: str
    dimension_value: str
    total_count: int
    failure_count: int
    failure_rate: float
    baseline_failure_rate: float
    deviation_pct: float
    z_score: float
    error_reasons: dict[str, int]
    error_sources: dict[str, int]


@dataclass
class InvestigationResult:
    incident_id: str
    merchant_id: str
    analysis_time: datetime
    top_affected_segments: list[DimensionBreakdown]
    dimensional_breakdown: dict[str, list[DimensionBreakdown]]
    temporal_pattern: list[dict]          # time-series of success rate
    error_distribution: dict[str, Any]
    affected_customers: int
    affected_transaction_value: float
    estimated_exposure: float
    avg_transaction_value: float
    summary: dict[str, Any]


class InvestigationEngine:

    def __init__(self):
        pass

    def _get_breakdown(
        self,
        session: Session,
        merchant_id: str,
        window_start: datetime,
        window_end: datetime,
        dimension: str,
    ) -> list[DimensionBreakdown]:
        """Get failure breakdown for a given dimension."""
        dim_map = {
            "payment_method": ("pm.type", "payment_methods pm ON t.payment_method_id = pm.id"),
            "bank": ("b.code", "banks b ON t.bank_id = b.id"),
            "device": ("d.type", "devices d ON t.device_id = d.id"),
            "location": ("l.city", "locations l ON t.location_id = l.id"),
            "error_reason": ("t.error_reason", None),
            "error_source": ("t.error_source", None),
        }

        if dimension not in dim_map:
            return []

        dim_col, join_clause = dim_map[dimension]
        join_part = f"JOIN {join_clause}" if join_clause else ""

        sql = text(f"""
            SELECT
                CAST({dim_col} AS TEXT) AS dim_val,
                COUNT(*) AS total,
                SUM(CASE WHEN t.status = 'FAILED' THEN 1 ELSE 0 END) AS failures,
                AVG(CAST(t.amount AS FLOAT)) AS avg_amount
            FROM transactions t
            {join_part}
            WHERE t.merchant_id = :merchant_id
              AND t.created_at BETWEEN :start AND :end
            GROUP BY {dim_col}
            ORDER BY failures DESC
        """)

        rows = session.execute(sql, {
            "merchant_id": merchant_id,
            "start": window_start,
            "end": window_end,
        }).fetchall()

        results = []
        for row in rows:
            if row.dim_val is None:
                continue
            total = int(row.total)
            failures = int(row.failures or 0)
            if total < 5:
                continue
            failure_rate = failures / total

            # Get baseline
            baseline_sql = text("""
                SELECT success_rate, std_dev FROM historical_baselines
                WHERE merchant_id = :merchant_id AND dimension = :dim AND dimension_value = :val
                LIMIT 1
            """)
            baseline_row = session.execute(baseline_sql, {
                "merchant_id": merchant_id,
                "dim": dimension,
                "val": str(row.dim_val),
            }).fetchone()

            baseline_success_rate = baseline_row.success_rate if baseline_row else 0.93
            baseline_std = baseline_row.std_dev if baseline_row else 0.05
            baseline_failure_rate = 1.0 - baseline_success_rate
            deviation_pct = (failure_rate - baseline_failure_rate) / max(baseline_failure_rate, 0.01) * 100

            import math
            se = baseline_std / math.sqrt(max(total, 1))
            z_score = (failure_rate - baseline_failure_rate) / max(se, 0.001)

            # Error reasons for this segment
            err_sql = text(f"""
                SELECT t.error_reason, COUNT(*) AS cnt
                FROM transactions t
                {join_part}
                WHERE t.merchant_id = :merchant_id
                  AND t.created_at BETWEEN :start AND :end
                  AND CAST({dim_col} AS TEXT) = :val
                  AND t.error_reason IS NOT NULL
                GROUP BY t.error_reason
                ORDER BY cnt DESC
                LIMIT 5
            """)
            err_rows = session.execute(err_sql, {
                "merchant_id": merchant_id,
                "start": window_start,
                "end": window_end,
                "val": str(row.dim_val),
            }).fetchall()
            error_reasons = {r.error_reason: int(r.cnt) for r in err_rows}

            # Error sources
            src_sql = text(f"""
                SELECT t.error_source, COUNT(*) AS cnt
                FROM transactions t
                {join_part}
                WHERE t.merchant_id = :merchant_id
                  AND t.created_at BETWEEN :start AND :end
                  AND CAST({dim_col} AS TEXT) = :val
                  AND t.error_source IS NOT NULL
                GROUP BY t.error_source
                ORDER BY cnt DESC
                LIMIT 5
            """)
            src_rows = session.execute(src_sql, {
                "merchant_id": merchant_id,
                "start": window_start,
                "end": window_end,
                "val": str(row.dim_val),
            }).fetchall()
            error_sources = {r.error_source: int(r.cnt) for r in src_rows}

            results.append(DimensionBreakdown(
                dimension=dimension,
                dimension_value=str(row.dim_val),
                total_count=total,
                failure_count=failures,
                failure_rate=failure_rate,
                baseline_failure_rate=baseline_failure_rate,
                deviation_pct=deviation_pct,
                z_score=z_score,
                error_reasons=error_reasons,
                error_sources=error_sources,
            ))

        return sorted(results, key=lambda x: x.deviation_pct, reverse=True)

    def _get_temporal_pattern(
        self,
        session: Session,
        merchant_id: str,
        window_start: datetime,
        window_end: datetime,
        bucket_minutes: int = 5,
    ) -> list[dict]:
        """Get time-series of success rate in N-minute buckets."""
        results = []
        cur_start = window_start
        while cur_start < window_end:
            cur_end = min(cur_start + timedelta(minutes=bucket_minutes), window_end)
            sql = text("""
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) AS successes
                FROM transactions
                WHERE merchant_id = :merchant_id
                  AND created_at BETWEEN :start AND :end
            """)
            r = session.execute(sql, {
                "merchant_id": merchant_id,
                "start": cur_start,
                "end": cur_end,
            }).fetchone()
            tot = int((r.total if r else 0) or 0)
            succ = int((r.successes if r else 0) or 0)
            if tot > 0:
                results.append({
                    "timestamp": cur_end.isoformat(),
                    "total": tot,
                    "successes": succ,
                    "success_rate": succ / tot,
                })
            cur_start = cur_end
        return results

    def investigate(
        self,
        session: Session,
        incident_id: str,
        merchant_id: str,
        window_start: datetime,
        window_end: datetime,
    ) -> InvestigationResult:
        """
        Full multi-dimensional investigation of an incident.
        Returns structured InvestigationResult.
        """
        dimensions = ["payment_method", "bank", "device", "location", "error_reason", "error_source"]
        dimensional_breakdown: dict[str, list[DimensionBreakdown]] = {}

        for dim in dimensions:
            breakdown = self._get_breakdown(session, merchant_id, window_start, window_end, dim)
            dimensional_breakdown[dim] = breakdown

        # Top affected segments across all dimensions (anomalous ones)
        top_segments = []
        for dim, breakdowns in dimensional_breakdown.items():
            if dim in ("error_reason", "error_source"):
                continue
            for b in breakdowns[:3]:  # top 3 per dimension
                if b.deviation_pct > 10:  # only meaningful deviations
                    top_segments.append(b)

        top_segments = sorted(top_segments, key=lambda x: x.deviation_pct, reverse=True)[:8]

        # Temporal pattern (last 2 hours, 5-min buckets)
        extended_start = window_start - timedelta(hours=1, minutes=30)
        temporal = self._get_temporal_pattern(session, merchant_id, extended_start, window_end, 5)

        # Error distribution in window
        err_sql = text("""
            SELECT error_reason, COUNT(*) AS cnt
            FROM transactions
            WHERE merchant_id = :merchant_id
              AND created_at BETWEEN :start AND :end
              AND status = 'FAILED'
              AND error_reason IS NOT NULL
            GROUP BY error_reason
            ORDER BY cnt DESC
        """)
        err_rows = session.execute(err_sql, {
            "merchant_id": merchant_id,
            "start": window_start,
            "end": window_end,
        }).fetchall()
        error_distribution = {"by_reason": {r.error_reason: int(r.cnt) for r in err_rows}}

        # Affected customers
        cust_sql = text("""
            SELECT COUNT(DISTINCT customer_id) AS cnt
            FROM transactions
            WHERE merchant_id = :merchant_id
              AND created_at BETWEEN :start AND :end
              AND status = 'FAILED'
        """)
        cust_row = session.execute(cust_sql, {
            "merchant_id": merchant_id,
            "start": window_start,
            "end": window_end,
        }).fetchone()
        affected_customers = int(cust_row.cnt or 0)

        # Value metrics
        value_sql = text("""
            SELECT
                SUM(CASE WHEN status = 'FAILED' THEN CAST(amount AS FLOAT) ELSE 0 END) AS failed_value,
                AVG(CAST(amount AS FLOAT)) AS avg_amount,
                COUNT(*) AS total
            FROM transactions
            WHERE merchant_id = :merchant_id
              AND created_at BETWEEN :start AND :end
        """)
        value_row = session.execute(value_sql, {
            "merchant_id": merchant_id,
            "start": window_start,
            "end": window_end,
        }).fetchone()

        failed_value = float(value_row.failed_value or 0)
        avg_txn_value = float(value_row.avg_amount or 0)

        # Estimated exposure: failed transaction value
        # Formula: (failed_transactions - expected_failures) * avg_amount
        baseline_sql = text("""
            SELECT success_rate FROM historical_baselines
            WHERE merchant_id = :merchant_id AND dimension = 'overall' AND dimension_value = 'ALL'
            LIMIT 1
        """)
        baseline_row = session.execute(baseline_sql, {"merchant_id": merchant_id}).fetchone()
        baseline_rate = baseline_row.success_rate if baseline_row else 0.93

        total_in_window = int(value_row.total or 0)
        expected_failures = total_in_window * (1 - baseline_rate)
        actual_failures_sql = text("""
            SELECT COUNT(*) AS cnt FROM transactions
            WHERE merchant_id = :merchant_id
              AND created_at BETWEEN :start AND :end
              AND status = 'FAILED'
        """)
        actual_fail_row = session.execute(actual_failures_sql, {
            "merchant_id": merchant_id, "start": window_start, "end": window_end
        }).fetchone()
        actual_failures = int(actual_fail_row.cnt or 0)

        incremental_failures = max(0, actual_failures - expected_failures)
        estimated_exposure = incremental_failures * avg_txn_value

        summary = {
            "total_transactions_in_window": total_in_window,
            "actual_failures": actual_failures,
            "expected_failures": round(expected_failures, 1),
            "incremental_failures": round(incremental_failures, 1),
            "top_affected_dimension": (
                top_segments[0].dimension if top_segments else "unknown"
            ),
            "top_affected_value": (
                top_segments[0].dimension_value if top_segments else "unknown"
            ),
        }

        return InvestigationResult(
            incident_id=incident_id,
            merchant_id=merchant_id,
            analysis_time=datetime.now(timezone.utc),
            top_affected_segments=top_segments,
            dimensional_breakdown=dimensional_breakdown,
            temporal_pattern=temporal,
            error_distribution=error_distribution,
            affected_customers=affected_customers,
            affected_transaction_value=failed_value,
            estimated_exposure=estimated_exposure,
            avg_transaction_value=avg_txn_value,
            summary=summary,
        )
