"""
PayPulse AI — Dashboard API
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from backend.database import get_db

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    """Main dashboard metrics."""
    now = datetime.now(timezone.utc)
    window_30 = now - timedelta(minutes=30)
    window_24h = now - timedelta(hours=24)

    # Current success rate (last 30 min)
    current_sql = text("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) AS successes,
            SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) AS failures
        FROM transactions
        WHERE created_at >= :window
    """)
    current = await db.execute(current_sql, {"window": window_30})
    curr_row = current.fetchone()

    total_30 = int((curr_row.total if curr_row else 0) or 0)
    success_30 = int((curr_row.successes if curr_row else 0) or 0)
    failure_30 = int((curr_row.failures if curr_row else 0) or 0)
    success_rate = success_30 / max(total_30, 1)
    failure_rate = failure_30 / max(total_30, 1)

    # 24h totals
    total_24h_sql = text("""
        SELECT COUNT(*) AS total FROM transactions WHERE created_at >= :window
    """)
    total_24h_row = await db.execute(total_24h_sql, {"window": window_24h})
    r24 = total_24h_row.fetchone()
    total_24h = int((r24.total if r24 else 0) or 0)

    # Active incidents
    incidents_sql = text("""
        SELECT
            SUM(CASE WHEN status != 'RESOLVED' THEN 1 ELSE 0 END) AS active,
            SUM(CASE WHEN status = 'RESOLVED' THEN 1 ELSE 0 END) AS resolved,
            COUNT(*) AS total
        FROM incidents
    """)
    inc_result = await db.execute(incidents_sql)
    inc_row = inc_result.fetchone()

    # Estimated exposure (open incidents)
    exposure_sql = text("""
        SELECT COALESCE(SUM(estimated_exposure), 0) AS total_exposure
        FROM incidents
        WHERE status != 'RESOLVED'
    """)
    exp_result = await db.execute(exposure_sql)
    exp_row = exp_result.fetchone()
    exposure = float((exp_row.total_exposure if exp_row else 0) or 0)

    # Success rate trend (last 3 hours in 10-min windows)
    trend = []
    for i in range(18, -1, -1):
        t_end = now - timedelta(minutes=i * 10)
        t_start = t_end - timedelta(minutes=10)
        t_sql = text("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) AS successes
            FROM transactions
            WHERE created_at BETWEEN :start AND :end
        """)
        t_res = await db.execute(t_sql, {"start": t_start, "end": t_end})
        t_r = t_res.fetchone()
        tot = int((t_r.total if t_r else 0) or 0)
        succ = int((t_r.successes if t_r else 0) or 0)
        if tot > 0:
            trend.append({
                "timestamp": t_end.isoformat(),
                "success_rate": round(succ / tot, 4),
                "failure_rate": round(1.0 - (succ / tot), 4),
                "total": tot,
            })

    # Payment method breakdown (last 30 min)
    pm_sql = text("""
        SELECT pm.type AS method,
               COUNT(*) AS total,
               SUM(CASE WHEN t.status = 'SUCCESS' THEN 1 ELSE 0 END) AS successes
        FROM transactions t
        JOIN payment_methods pm ON t.payment_method_id = pm.id
        WHERE t.created_at >= :window
        GROUP BY pm.type
        ORDER BY total DESC
    """)
    pm_result = await db.execute(pm_sql, {"window": window_30})
    pm_rows = pm_result.fetchall()
    payment_methods = [
        {
            "method": str(r.method),
            "total": int(r.total),
            "success_rate": float(r.successes or 0) / max(float(r.total), 1),
            "failure_rate": 1 - float(r.successes or 0) / max(float(r.total), 1),
        }
        for r in pm_rows
    ]

    # Baseline for comparison
    baseline_sql = text("""
        SELECT success_rate FROM historical_baselines
        WHERE dimension = 'overall' AND dimension_value = 'ALL'
        LIMIT 1
    """)
    baseline_result = await db.execute(baseline_sql)
    baseline_row = baseline_result.fetchone()
    baseline_rate = float(baseline_row.success_rate if baseline_row else 0.93)

    return {
        "current_success_rate": round(success_rate, 4),
        "current_failure_rate": round(failure_rate, 4),
        "baseline_success_rate": round(baseline_rate, 4),
        "transactions_last_30m": total_30,
        "transactions_last_24h": total_24h,
        "active_incidents": int((inc_row.active if inc_row else 0) or 0),
        "resolved_incidents": int((inc_row.resolved if inc_row else 0) or 0),
        "estimated_revenue_exposure": round(exposure, 2),
        "success_rate_trend": trend,
        "payment_method_breakdown": payment_methods,
        "is_degraded": success_rate < (baseline_rate - 0.05),
        "timestamp": now.isoformat(),
    }
