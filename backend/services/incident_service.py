"""
PayPulse AI — Incident Service

Orchestrates the full incident lifecycle:
Detection → Creation → Investigation → Recommendation → Approval → Action → Verification
"""
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.models import (
    Incident, IncidentSignal, IncidentHypothesis, IncidentEvidence,
    Recommendation, ActionResult, AuditLog, IncidentType,
    IncidentSeverity, IncidentStatus, ActionType, ApprovalStatus, VerificationResult
)
from backend.detection.anomaly_detector import AnomalyDetector, DetectionResult
from backend.investigation.investigation_engine import InvestigationEngine


class IncidentService:

    def __init__(self):
        self.detector = AnomalyDetector()
        self.investigation_engine = InvestigationEngine()

    def run_detection(self, session: Session, merchant_id: str) -> Optional[Incident]:
        """
        Run anomaly detection for a merchant.
        If an anomaly is detected, create and return an Incident.
        Returns None if no incident warranted.
        """
        result: DetectionResult = self.detector.detect(session, merchant_id)

        if not result.is_anomalous:
            return None

        # Check if there's already an open incident for this merchant
        existing = (
            session.query(Incident)
            .filter_by(merchant_id=merchant_id)
            .filter(Incident.status.in_([
                IncidentStatus.DETECTED, IncidentStatus.INVESTIGATING,
                IncidentStatus.ACTION_REQUIRED, IncidentStatus.MITIGATING,
                IncidentStatus.MONITORING,
            ]))
            .first()
        )
        if existing:
            # Update existing incident stats
            existing.current_success_rate = result.current_success_rate
            existing.affected_transaction_count = result.affected_transaction_count
            session.flush()
            return existing

        # Create new incident
        incident = self._create_incident(session, merchant_id, result)
        return incident

    def _create_incident(
        self, session: Session, merchant_id: str, detection: DetectionResult
    ) -> Incident:
        """Create a new incident from detection result."""
        # Find incident type
        # Determine type from most anomalous signal
        anomalous_signals = [s for s in detection.signals if s.is_anomalous]
        primary_signal = (
            max(anomalous_signals, key=lambda s: abs(s.deviation_pct))
            if anomalous_signals else None
        )

        type_map = {
            "payment_method": "PAYMENT_METHOD_DEGRADATION",
            "bank": "BANK_DEGRADATION",
            "device": "DEVICE_DEGRADATION",
            "location": "GEOGRAPHIC_DEGRADATION",
            "overall": "OVERALL_DEGRADATION",
        }
        type_name = (
            type_map.get(primary_signal.dimension, "OVERALL_DEGRADATION")
            if primary_signal else "OVERALL_DEGRADATION"
        )

        incident_type = session.query(IncidentType).filter_by(name=type_name).first()

        # Estimate exposure
        value_sql = text("""
            SELECT AVG(CAST(amount AS FLOAT)) AS avg_amount FROM transactions
            WHERE merchant_id = :merchant_id AND created_at BETWEEN :start AND :end
        """)
        val_row = session.execute(value_sql, {
            "merchant_id": merchant_id,
            "start": detection.window_start,
            "end": detection.window_end,
        }).fetchone()
        avg_amount = float(val_row.avg_amount or 0)

        baseline_rate = detection.baseline_success_rate or 0.93
        current_rate = detection.current_success_rate or 0
        total = detection.affected_transaction_count
        expected_failures = total * (1 - baseline_rate)

        # For simplicity: exposure = incremental_failures * avg_amount
        incremental_failures = max(0, total - (total * baseline_rate / max(current_rate, 0.01)))
        # Actually compute properly:
        count_sql = text("""
            SELECT COUNT(*) AS total FROM transactions
            WHERE merchant_id = :merchant_id AND created_at BETWEEN :start AND :end
        """)
        cnt_row = session.execute(count_sql, {
            "merchant_id": merchant_id, "start": detection.window_start, "end": detection.window_end
        }).fetchone()
        total_window = int(cnt_row.total or 0)
        actual_failures = detection.affected_transaction_count
        expected_fail = total_window * (1 - baseline_rate)
        incremental = max(0, actual_failures - expected_fail)
        estimated_exposure = Decimal(str(round(incremental * avg_amount, 2)))

        # Build title
        dim_val = primary_signal.dimension_value if primary_signal else "Overall"
        deg_pct = abs(primary_signal.deviation_pct) if primary_signal else 0
        title = (
            f"Payment degradation detected: {dim_val} failure rate increased by {deg_pct:.1f}%"
        )

        incident = Incident(
            id=str(uuid.uuid4()),
            merchant_id=merchant_id,
            incident_type_id=incident_type.id if incident_type else None,
            severity=detection.overall_severity,
            status=IncidentStatus.DETECTED,
            title=title,
            description=(
                f"Payment success rate dropped from {detection.baseline_success_rate*100:.1f}% "
                f"to {detection.current_success_rate*100:.1f}% "
                f"in the last {30} minutes."
            ),
            start_time=detection.window_start,
            detected_at=datetime.now(timezone.utc),
            current_success_rate=detection.current_success_rate,
            baseline_success_rate=detection.baseline_success_rate,
            affected_transaction_count=actual_failures,
            estimated_exposure=estimated_exposure,
        )
        session.add(incident)
        session.flush()

        # Store signals
        for sig in [s for s in detection.signals if s.is_anomalous]:
            signal = IncidentSignal(
                id=str(uuid.uuid4()),
                incident_id=incident.id,
                dimension=sig.dimension,
                dimension_value=sig.dimension_value,
                current_rate=sig.current_rate,
                baseline_rate=sig.baseline_rate,
                deviation_pct=sig.deviation_pct,
                z_score=sig.z_score,
                transaction_count=sig.transaction_count,
            )
            session.add(signal)

        # Audit log
        self._log_audit(
            session,
            incident_id=incident.id,
            actor="SYSTEM",
            action="INCIDENT_DETECTED",
            reason="Statistical anomaly detected by detection engine",
            result=f"Incident {incident.id} created with severity {detection.overall_severity}",
            metadata={
                "current_rate": detection.current_success_rate,
                "baseline_rate": detection.baseline_success_rate,
                "anomalous_signals": len([s for s in detection.signals if s.is_anomalous]),
            }
        )

        session.flush()
        print(f"[incident] Created incident {incident.id} severity={detection.overall_severity}")
        return incident

    def update_investigation(
        self,
        session: Session,
        incident_id: str,
        investigation_report: dict,
    ) -> Incident:
        """Store AI investigation report and hypotheses on the incident."""
        incident = session.query(Incident).filter_by(id=incident_id).first()
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")

        incident.investigation_report = investigation_report
        incident.status = IncidentStatus.ACTION_REQUIRED

        # Store hypotheses
        for i, cause in enumerate(investigation_report.get("candidate_causes", [])):
            hyp = IncidentHypothesis(
                id=str(uuid.uuid4()),
                incident_id=incident_id,
                title=cause.get("hypothesis", ""),
                description=", ".join(cause.get("supporting_evidence", [])),
                confidence=cause.get("confidence", 0.5),
                is_primary=(i == 0),
            )
            session.add(hyp)

        # Store key evidence items
        for ev_text in investigation_report.get("key_evidence", []):
            ev = IncidentEvidence(
                id=str(uuid.uuid4()),
                incident_id=incident_id,
                evidence_type="METRIC",
                title=ev_text[:200],
                description=ev_text,
                strength=investigation_report.get("confidence", 0.7),
            )
            session.add(ev)

        # Exposure estimate
        impact = investigation_report.get("business_impact", {})
        if impact.get("estimated_exposure_inr"):
            incident.estimated_exposure = Decimal(str(impact["estimated_exposure_inr"]))
        if impact.get("affected_transactions"):
            incident.affected_transaction_count = impact["affected_transactions"]

        # Create recommendation
        action_type_str = investigation_report.get("recommended_action", "MONITOR_PAYMENT_HEALTH")
        try:
            action_type = ActionType[action_type_str]
        except KeyError:
            action_type = ActionType.MONITOR_PAYMENT_HEALTH

        rec = Recommendation(
            id=str(uuid.uuid4()),
            incident_id=incident_id,
            action_type=action_type,
            title=f"AI-recommended action: {action_type_str}",
            description=investigation_report.get("reasoning_summary", ""),
            reasoning=investigation_report.get("reasoning_summary", ""),
            expected_improvement="Estimated 10-20% improvement in payment success rate",
            requires_approval=True,
            risk_level="LOW" if action_type in (
                ActionType.NOTIFY_MERCHANT, ActionType.MONITOR_PAYMENT_HEALTH
            ) else "MEDIUM",
        )
        session.add(rec)

        self._log_audit(
            session,
            incident_id=incident_id,
            actor="AI_AGENT",
            action="INVESTIGATION_COMPLETED",
            reason="AI agent completed investigation using tool-based evidence gathering",
            result=f"Generated {len(investigation_report.get('candidate_causes', []))} hypotheses",
        )

        session.flush()
        return incident

    def approve_recommendation(
        self,
        session: Session,
        recommendation_id: str,
        approved_by: str,
    ) -> Recommendation:
        rec = session.query(Recommendation).filter_by(id=recommendation_id).first()
        if not rec:
            raise ValueError(f"Recommendation {recommendation_id} not found")

        rec.approval_status = ApprovalStatus.APPROVED
        rec.approved_by = approved_by
        rec.approved_at = datetime.now(timezone.utc)

        incident = session.query(Incident).filter_by(id=rec.incident_id).first()
        if incident:
            incident.status = IncidentStatus.MITIGATING

        self._log_audit(
            session,
            incident_id=rec.incident_id,
            actor=approved_by,
            action="RECOMMENDATION_APPROVED",
            reason=f"Merchant approved action: {rec.action_type}",
            approval_status="APPROVED",
            result="Action queued for execution",
        )
        session.flush()
        return rec

    def reject_recommendation(
        self,
        session: Session,
        recommendation_id: str,
        rejected_by: str,
        reason: str,
    ) -> Recommendation:
        rec = session.query(Recommendation).filter_by(id=recommendation_id).first()
        if not rec:
            raise ValueError(f"Recommendation {recommendation_id} not found")

        rec.approval_status = ApprovalStatus.REJECTED
        rec.rejection_reason = reason

        incident = session.query(Incident).filter_by(id=rec.incident_id).first()
        if incident:
            incident.status = IncidentStatus.ESCALATED

        self._log_audit(
            session,
            incident_id=rec.incident_id,
            actor=rejected_by,
            action="RECOMMENDATION_REJECTED",
            reason=reason,
            approval_status="REJECTED",
        )
        session.flush()
        return rec

    def execute_action(
        self,
        session: Session,
        recommendation_id: str,
        executed_by: str = "SYSTEM",
    ) -> ActionResult:
        """Simulate action execution and record result."""
        rec = session.query(Recommendation).filter_by(id=recommendation_id).first()
        if not rec:
            raise ValueError(f"Recommendation {recommendation_id} not found")

        if rec.approval_status != ApprovalStatus.APPROVED:
            raise ValueError("Recommendation must be approved before execution")

        incident = session.query(Incident).filter_by(id=rec.incident_id).first()

        # Simulate action effect: mark scenario as "recovery" in synthetic data
        # In a real system this would call actual payment gateway APIs
        before_rate = incident.current_success_rate or 0.75

        # Simulate improvement based on action type
        import random
        improvement_map = {
            ActionType.RECOMMEND_ALTERNATIVE_PAYMENT_METHOD: (0.08, 0.15),
            ActionType.ENABLE_RETRY_LOGIC: (0.05, 0.10),
            ActionType.ROUTE_TO_BACKUP_PROVIDER: (0.12, 0.20),
            ActionType.NOTIFY_MERCHANT: (0.02, 0.05),
            ActionType.MONITOR_PAYMENT_HEALTH: (0.0, 0.02),
            ActionType.CREATE_SUPPORT_INCIDENT: (0.03, 0.08),
            ActionType.ESCALATE_TO_PAYMENT_OPERATIONS: (0.05, 0.12),
        }

        lo, hi = improvement_map.get(rec.action_type, (0.05, 0.10))
        improvement = random.uniform(lo, hi)
        after_rate = min(0.97, before_rate + improvement + random.uniform(-0.02, 0.02))

        abs_improvement = after_rate - before_rate
        pct_improvement = abs_improvement / max(before_rate, 0.01) * 100

        if abs_improvement >= 0.10:
            ver_result = VerificationResult.IMPROVED
        elif abs_improvement >= 0.03:
            ver_result = VerificationResult.PARTIALLY_IMPROVED
        elif abs_improvement >= 0:
            ver_result = VerificationResult.NO_IMPROVEMENT
        else:
            ver_result = VerificationResult.WORSENED

        action_result = ActionResult(
            id=str(uuid.uuid4()),
            recommendation_id=recommendation_id,
            incident_id=rec.incident_id,
            executed_by=executed_by,
            success_rate_before=before_rate,
            success_rate_after=after_rate,
            absolute_improvement=abs_improvement,
            pct_improvement=pct_improvement,
            verification_result=ver_result,
            verification_details={
                "action_type": rec.action_type.value,
                "simulated": True,
                "improvement_summary": f"Success rate: {before_rate*100:.1f}% → {after_rate*100:.1f}%",
                "recommendation": (
                    "Incident resolved" if ver_result == VerificationResult.IMPROVED
                    else "Consider escalation"
                ),
            }
        )
        session.add(action_result)

        # Update incident
        incident.current_success_rate = after_rate
        if ver_result in (VerificationResult.IMPROVED, VerificationResult.PARTIALLY_IMPROVED):
            incident.status = IncidentStatus.MONITORING
        else:
            incident.status = IncidentStatus.ESCALATED

        if ver_result == VerificationResult.IMPROVED and after_rate >= 0.90:
            incident.status = IncidentStatus.RESOLVED
            incident.resolved_at = datetime.now(timezone.utc)

        self._log_audit(
            session,
            incident_id=rec.incident_id,
            actor=executed_by,
            action="ACTION_EXECUTED",
            reason=f"Executed {rec.action_type.value}",
            result=f"Verification: {ver_result.value} | Rate: {before_rate:.3f} → {after_rate:.3f}",
            metadata={
                "action_type": rec.action_type.value,
                "before_rate": before_rate,
                "after_rate": after_rate,
                "verification_result": ver_result.value,
            }
        )
        session.flush()
        return action_result

    def get_incident_timeline(self, session: Session, incident_id: str) -> list[dict]:
        """Return chronological event timeline for an incident."""
        logs = (
            session.query(AuditLog)
            .filter_by(incident_id=incident_id)
            .order_by(AuditLog.created_at)
            .all()
        )

        timeline = []
        for log in logs:
            ts = log.created_at.isoformat() if hasattr(log.created_at, "isoformat") else str(log.created_at) if log.created_at else None
            timeline.append({
                "timestamp": ts,
                "actor": log.actor,
                "action": log.action,
                "description": log.reason or log.action,
                "result": log.result,
                "metadata": log.metadata,
            })

        # Also include detection start from incident
        incident = session.query(Incident).filter_by(id=incident_id).first()
        if incident and incident.start_time:
            ts_start = incident.start_time.isoformat() if hasattr(incident.start_time, "isoformat") else str(incident.start_time)
            timeline.insert(0, {
                "timestamp": ts_start,
                "actor": "SYSTEM",
                "action": "ANOMALY_START",
                "description": "Payment anomaly began",
                "result": f"Success rate: {(incident.current_success_rate or 0)*100:.1f}%",
            })

        return sorted([t for t in timeline if t.get("timestamp")], key=lambda x: x["timestamp"])

    def resolve_incident(self, session: Session, incident_id: str) -> Incident:
        incident = session.query(Incident).filter_by(id=incident_id).first()
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = datetime.now(timezone.utc)
        self._log_audit(
            session, incident_id=incident_id,
            actor="SYSTEM", action="INCIDENT_RESOLVED",
            reason="Payment metrics recovered to acceptable levels",
            result="Incident closed",
        )
        session.flush()
        return incident

    def _log_audit(
        self,
        session: Session,
        incident_id: str,
        actor: str,
        action: str,
        reason: str = "",
        approval_status: str = "",
        result: str = "",
        metadata: dict = None,
    ):
        log = AuditLog(
            id=str(uuid.uuid4()),
            incident_id=incident_id,
            actor=actor,
            action=action,
            reason=reason,
            approval_status=approval_status,
            result=result,
            metadata=metadata or {},
        )
        session.add(log)
