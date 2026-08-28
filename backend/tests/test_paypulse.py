"""
PayPulse AI — Unit and Integration Test Suite
Tests anomaly detection, investigation engine, impact calculation,
incident service lifecycle, and API endpoints.
"""
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.database import sync_engine
from backend.models import (
    Merchant, IncidentSeverity, IncidentStatus, ActionType, ApprovalStatus
)
from backend.detection.anomaly_detector import AnomalyDetector
from backend.investigation.investigation_engine import InvestigationEngine
from backend.services.incident_service import IncidentService


@pytest.fixture(scope="module")
def db_session():
    with Session(sync_engine) as session:
        yield session


def test_merchant_and_baselines_exist(db_session: Session):
    """Verify seed data created active merchant and baselines."""
    merchant = db_session.execute(text("SELECT * FROM merchants LIMIT 1")).fetchone()
    assert merchant is not None, "Merchant should exist in database"

    baselines = db_session.execute(text("SELECT COUNT(*) AS cnt FROM historical_baselines")).fetchone()
    assert baselines.cnt > 0, "Historical baselines should be computed"


def test_anomaly_detection_logic(db_session: Session):
    """Verify statistical anomaly detector on baseline and incident windows."""
    detector = AnomalyDetector()
    merchant = db_session.execute(text("SELECT id FROM merchants LIMIT 1")).fetchone()
    assert merchant is not None

    result = detector.detect(db_session, str(merchant.id), window_minutes=60)
    assert result.current_success_rate > 0
    assert result.baseline_success_rate > 0.85
    assert len(result.signals) > 0
    assert result.overall_severity in [
        IncidentSeverity.LOW, IncidentSeverity.MEDIUM, IncidentSeverity.HIGH, IncidentSeverity.CRITICAL
    ]


def test_investigation_engine_multidimensional(db_session: Session):
    """Verify investigation engine produces dimensional breakdowns and evidence."""
    inv_engine = InvestigationEngine()
    merchant = db_session.execute(text("SELECT id FROM merchants LIMIT 1")).fetchone()
    assert merchant is not None

    now = datetime.now(timezone.utc)
    result = inv_engine.investigate(
        db_session,
        incident_id="test_incident",
        merchant_id=str(merchant.id),
        window_start=now - timedelta(hours=2),
        window_end=now,
    )

    assert result.incident_id == "test_incident"
    assert "payment_method" in result.dimensional_breakdown
    assert "bank" in result.dimensional_breakdown
    assert "device" in result.dimensional_breakdown
    assert "location" in result.dimensional_breakdown
    assert result.avg_transaction_value > 0
    assert len(result.temporal_pattern) > 0


def test_business_impact_formula(db_session: Session):
    """Verify business impact formula calculates exposure transparently."""
    inv_engine = InvestigationEngine()
    merchant = db_session.execute(text("SELECT id FROM merchants LIMIT 1")).fetchone()
    assert merchant is not None

    now = datetime.now(timezone.utc)
    result = inv_engine.investigate(
        db_session,
        incident_id="test_impact",
        merchant_id=str(merchant.id),
        window_start=now - timedelta(hours=1),
        window_end=now,
    )

    assert result.estimated_exposure >= 0
    assert result.affected_customers >= 0
    assert result.summary["actual_failures"] >= 0
    assert "incremental_failures" in result.summary


def test_incident_lifecycle_workflow(db_session: Session):
    """Test full workflow: create incident -> approve action -> execute -> verify."""
    inc_service = IncidentService()
    merchant = db_session.execute(text("SELECT id FROM merchants LIMIT 1")).fetchone()
    assert merchant is not None
    merchant_id = str(merchant.id)

    # 1. Detection & Creation
    incident = inc_service.run_detection(db_session, merchant_id)
    assert incident is not None, "Incident should be created or retrieved"

    # 2. Add synthetic investigation report
    mock_report = {
        "incident_id": str(incident.id),
        "incident_summary": "Test UPI degradation",
        "what_changed": "UPI success dropped by 30pp",
        "when_it_started": str(incident.start_time),
        "affected_segments": ["payment_method = UPI (+35% failures)"],
        "key_evidence": ["UPI failure rate 45%"],
        "candidate_causes": [
            {
                "hypothesis": "UPI Network Timeout",
                "confidence": 0.85,
                "supporting_evidence": ["Error TIMEOUT concentrated in UPI"]
            }
        ],
        "confidence": 0.85,
        "business_impact": {
            "affected_transactions": 50,
            "estimated_exposure_inr": 25000.0,
            "customers_affected": 40,
            "severity": "HIGH"
        },
        "recommended_action": "RECOMMEND_ALTERNATIVE_PAYMENT_METHOD",
        "reasoning_summary": "High confidence UPI network issue",
        "limitations": "Test run",
        "next_steps": ["Recommend alternative payment method"]
    }

    updated_inc = inc_service.update_investigation(db_session, str(incident.id), mock_report)
    assert updated_inc.status == IncidentStatus.ACTION_REQUIRED

    # 3. Check Recommendation Created
    rec = db_session.execute(
        text("SELECT * FROM recommendations WHERE incident_id = :id LIMIT 1"),
        {"id": str(incident.id)}
    ).fetchone()
    assert rec is not None
    assert rec.approval_status == ApprovalStatus.PENDING.value

    # 4. Human Approval
    approved_rec = inc_service.approve_recommendation(db_session, str(rec.id), "qa_tester@paypulse.ai")
    assert approved_rec.approval_status == ApprovalStatus.APPROVED

    # 5. Execution & Verification Loop
    action_res = inc_service.execute_action(db_session, str(rec.id), "TEST_SYSTEM")
    assert action_res.success_rate_after >= action_res.success_rate_before
    assert action_res.verification_result is not None
    db_session.commit()
