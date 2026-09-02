"""
PayPulse AI — Audit Log API
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from backend.database import get_db

router = APIRouter(tags=["audit"])


@router.get("/audit-logs")
async def get_audit_logs(
    incident_id: str = Query(None),
    limit: int = Query(100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    """Get audit log entries with optional incident filter."""
    query = """
        SELECT al.*, i.title as incident_title
        FROM audit_logs al
        LEFT JOIN incidents i ON al.incident_id = i.id
        WHERE 1=1
    """
    params = {"limit": limit, "offset": offset}

    if incident_id:
        query += " AND al.incident_id = :incident_id"
        params["incident_id"] = incident_id

    query += " ORDER BY al.created_at DESC LIMIT :limit OFFSET :offset"

    result = await db.execute(text(query), params)
    rows = result.fetchall()

    return {
        "audit_logs": [
            {
                "id": str(r.id),
                "incident_id": str(r.incident_id) if r.incident_id else None,
                "incident_title": r.incident_title,
                "actor": r.actor,
                "action": r.action,
                "reason": r.reason,
                "approval_status": r.approval_status,
                "result": r.result,
                "metadata": r.metadata,
                "created_at": (
                    r.created_at.isoformat()
                    if hasattr(r.created_at, "isoformat")
                    else str(r.created_at) if r.created_at else None
                ),
            }
            for r in rows
        ],
        "total": len(rows),
    }
