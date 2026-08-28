"""
PayPulse AI — Simulator API
Controls the payment simulation and demo mode.
"""
import threading
import time
import random
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session as SyncSession
from sqlalchemy import text

from backend.database import get_db, sync_engine
from backend.config import settings
from backend.models import (
    Transaction, PaymentEvent, TransactionStatus, EventType,
    IncidentStatus
)
from backend.services.incident_service import IncidentService

router = APIRouter(prefix="/simulator", tags=["simulator"])

# Global simulator state
_sim_state = {
    "running": False,
    "mode": "stopped",      # normal / incident / recovery
    "scenario": None,
    "thread": None,
    "stats": {
        "total_generated": 0,
        "success_count": 0,
        "failure_count": 0,
    }
}

incident_service = IncidentService()


class SimulatorStartRequest(BaseModel):
    mode: str = "normal"    # normal / incident / recovery
    tps: float = 2.0        # transactions per second


class ScenarioRequest(BaseModel):
    scenario: str = "upi_degradation"


@router.get("/status")
async def get_simulator_status():
    """Get current simulator status."""
    return {
        "running": _sim_state["running"],
        "mode": _sim_state["mode"],
        "scenario": _sim_state["scenario"],
        "stats": _sim_state["stats"],
    }


@router.post("/start")
async def start_simulator(body: SimulatorStartRequest):
    """Start the payment simulator."""
    if _sim_state["running"]:
        _sim_state["mode"] = body.mode
        return {"status": "mode_changed", "mode": body.mode}

    _sim_state["running"] = True
    _sim_state["mode"] = body.mode

    thread = threading.Thread(
        target=_simulator_loop,
        args=(body.tps,),
        daemon=True
    )
    _sim_state["thread"] = thread
    thread.start()

    return {"status": "started", "mode": body.mode, "tps": body.tps}


@router.post("/stop")
async def stop_simulator():
    """Stop the payment simulator."""
    _sim_state["running"] = False
    _sim_state["mode"] = "stopped"
    return {"status": "stopped"}


@router.post("/scenario")
async def trigger_scenario(body: ScenarioRequest):
    """Trigger a specific incident scenario."""
    from data_generator.config import SCENARIOS
    if body.scenario not in SCENARIOS:
        raise HTTPException(status_code=400, detail=f"Unknown scenario: {body.scenario}")

    _sim_state["mode"] = "incident"
    _sim_state["scenario"] = body.scenario

    if not _sim_state["running"]:
        _sim_state["running"] = True
        thread = threading.Thread(
            target=_simulator_loop,
            args=(settings.SIM_TPS,),
            daemon=True
        )
        _sim_state["thread"] = thread
        thread.start()

    return {"status": "scenario_triggered", "scenario": body.scenario}


@router.post("/demo")
async def run_demo():
    """
    One-click full demo story.
    Runs through: NORMAL → INCIDENT → INVESTIGATION → RECOMMENDATION → APPROVAL → ACTION → RECOVERY
    """
    import threading

    def _demo_thread():
        _run_full_demo_story()

    t = threading.Thread(target=_demo_thread, daemon=True)
    t.start()

    return {
        "status": "demo_started",
        "message": "Full demo story is running. Poll /api/incidents for updates.",
        "steps": [
            "1. Normal traffic (30s)",
            "2. UPI degradation triggered",
            "3. Anomaly detected (auto)",
            "4. AI investigation triggered",
            "5. Recommendation generated",
            "6. Auto-approval (demo mode)",
            "7. Action executed",
            "8. Recovery monitored",
            "9. Incident resolved",
        ]
    }


@router.post("/detect")
async def run_detection(db: AsyncSession = Depends(get_db)):
    """Manually trigger anomaly detection run."""
    from sqlalchemy.orm import Session as SyncSession
    with SyncSession(sync_engine) as session:
        # Get first merchant
        result = session.execute(text("SELECT id FROM merchants LIMIT 1"))
        row = result.fetchone()
        if not row:
            return {"message": "No merchants found. Run seed first."}

        merchant_id = str(row.id)
        incident = incident_service.run_detection(session, merchant_id)
        session.commit()

        if incident:
            return {
                "detected": True,
                "incident_id": str(incident.id),
                "severity": incident.severity.value if hasattr(incident.severity, 'value') else incident.severity,
                "status": incident.status.value if hasattr(incident.status, 'value') else incident.status,
                "message": f"Incident detected: {incident.title}"
            }
        else:
            return {"detected": False, "message": "No anomaly detected in current window."}


def _simulator_loop(tps: float):
    """Main simulator loop — generates synthetic transactions."""
    from data_generator.config import (
        BANKS, BANK_WEIGHTS, LOCATION_WEIGHTS, DEVICE_WEIGHTS,
        PAYMENT_METHOD_WEIGHTS, AMOUNT_RANGES, ERROR_SOURCES, ERROR_STEPS,
        ERROR_REASONS, NORMAL_SUCCESS_RATE, SCENARIOS
    )

    with SyncSession(sync_engine) as session:
        # Load reference entities
        merchants = session.execute(text("SELECT id FROM merchants LIMIT 1")).fetchall()
        if not merchants:
            print("[sim] No merchants found. Please run seed first.")
            return

        merchant_id = str(merchants[0].id)

        customers = session.execute(
            text("SELECT id FROM customers WHERE merchant_id = :mid LIMIT 1000"),
            {"mid": merchant_id}
        ).fetchall()

        pms = session.execute(text("SELECT id, type FROM payment_methods")).fetchall()
        banks = session.execute(text("SELECT id, code FROM banks")).fetchall()
        devices = session.execute(text("SELECT id, type FROM devices")).fetchall()
        locations = session.execute(text("SELECT id, city FROM locations")).fetchall()

        if not customers or not pms:
            print("[sim] Reference data missing. Run seed first.")
            return

        pm_dict = {pm.type: pm.id for pm in pms}
        bank_dict = {b.code: b.id for b in banks}

        sleep_time = 1.0 / max(tps, 0.1)

        while _sim_state["running"]:
            try:
                mode = _sim_state["mode"]
                scenario = None
                if mode == "incident" and _sim_state["scenario"]:
                    scenario = SCENARIOS.get(_sim_state["scenario"])

                # Pick payment method
                pm_type_str = random.choices(
                    list(PAYMENT_METHOD_WEIGHTS.keys()),
                    weights=list(PAYMENT_METHOD_WEIGHTS.values())
                )[0]
                pm_id = pm_dict.get(pm_type_str)
                if not pm_id:
                    pm_id = pms[0].id

                # Pick bank
                bank_code = random.choices([b[0] for b in BANKS], weights=BANK_WEIGHTS)[0]
                bank_id = bank_dict.get(bank_code)
                if not bank_id:
                    bank_id = banks[0].id

                # Pick device
                dev_type = random.choices(
                    list(DEVICE_WEIGHTS.keys()),
                    weights=list(DEVICE_WEIGHTS.values())
                )[0]
                dev_id = random.choice([d.id for d in devices if d.type == dev_type] or [devices[0].id])

                # Pick location
                loc_idx = random.choices(range(len(locations)), weights=LOCATION_WEIGHTS)[0]
                loc = locations[loc_idx]

                # Determine success
                success = True
                if scenario:
                    dim = scenario["affected_dimension"]
                    val = scenario["affected_value"]
                    lo, hi = scenario["success_rate_override"]

                    affected = (
                        (dim == "payment_method" and pm_type_str == val) or
                        (dim == "bank" and bank_code == val) or
                        (dim == "device" and dev_type == val) or
                        (dim == "location" and loc.city == val) or
                        (dim == "overall")
                    )

                    if affected:
                        noise = random.gauss(0, 0.05)
                        rate = max(0.1, min(0.99, random.uniform(lo, hi) + noise))
                        success = random.random() < rate
                    else:
                        lo2, hi2 = NORMAL_SUCCESS_RATE.get(pm_type_str, (0.90, 0.95))
                        success = random.random() < random.uniform(lo2, hi2)
                else:
                    lo, hi = NORMAL_SUCCESS_RATE.get(pm_type_str, (0.90, 0.95))
                    success = random.random() < random.uniform(lo, hi)

                # Amount
                lo_a, hi_a = AMOUNT_RANGES.get(pm_type_str, (100, 10000))
                amount = round(random.uniform(lo_a, hi_a), 2)

                # Error info
                error_source, error_step, error_reason = None, None, None
                if not success:
                    error_source = random.choice(ERROR_SOURCES)
                    error_step = random.choice(ERROR_STEPS)
                    if scenario and scenario.get("error_reason_concentration") and random.random() < 0.65:
                        error_reason = scenario["error_reason_concentration"]
                    else:
                        error_reason = random.choice(ERROR_REASONS)
                    if scenario and scenario.get("error_source_concentration") and random.random() < 0.65:
                        error_source = scenario["error_source_concentration"]

                customer = random.choice(customers)
                now = datetime.now(timezone.utc)
                txn_id = str(uuid.uuid4())

                txn = Transaction(
                    id=txn_id,
                    merchant_id=merchant_id,
                    customer_id=str(customer.id),
                    amount=Decimal(str(amount)),
                    currency="INR",
                    payment_method_id=str(pm_id),
                    bank_id=str(bank_id),
                    device_id=str(dev_id),
                    location_id=str(loc.id),
                    status=TransactionStatus.SUCCESS if success else TransactionStatus.FAILED,
                    error_source=error_source,
                    error_step=error_step,
                    error_reason=error_reason,
                    scenario_tag=mode,
                    created_at=now,
                )
                session.add(txn)

                # Events
                for evt_type, offset_s in [
                    (EventType.PAYMENT_INITIATED, 0),
                    (EventType.PAYMENT_PROCESSING, 1),
                    (EventType.PAYMENT_SUCCESS if success else EventType.PAYMENT_FAILURE, 3),
                ]:
                    session.add(PaymentEvent(
                        id=str(uuid.uuid4()),
                        transaction_id=txn_id,
                        event_type=evt_type,
                        created_at=now + timedelta(seconds=offset_s),
                        metadata={"error_reason": error_reason} if not success and evt_type == EventType.PAYMENT_FAILURE else {},
                    ))

                session.commit()

                # Update stats
                _sim_state["stats"]["total_generated"] += 1
                if success:
                    _sim_state["stats"]["success_count"] += 1
                else:
                    _sim_state["stats"]["failure_count"] += 1

                time.sleep(sleep_time)

            except Exception as e:
                print(f"[sim] Error: {e}")
                time.sleep(1)


def _run_full_demo_story():
    """Run the complete demo story end-to-end."""
    print("[demo] Starting full demo story...")

    with SyncSession(sync_engine) as session:
        merchant = session.execute(text("SELECT id FROM merchants LIMIT 1")).fetchone()
        if not merchant:
            print("[demo] No merchant found. Run seed first.")
            return
        merchant_id = str(merchant.id)

    # Step 1: Normal for 20 seconds
    print("[demo] Step 1: Normal traffic...")
    _sim_state["running"] = True
    _sim_state["mode"] = "normal"
    _sim_state["scenario"] = None
    t = threading.Thread(target=_simulator_loop, args=(3.0,), daemon=True)
    _sim_state["thread"] = t
    t.start()
    time.sleep(20)

    # Step 2: Trigger UPI degradation
    print("[demo] Step 2: Triggering UPI degradation...")
    _sim_state["mode"] = "incident"
    _sim_state["scenario"] = "upi_degradation"
    time.sleep(40)  # Let degradation accumulate

    # Step 3: Run detection
    print("[demo] Step 3: Running detection...")
    with SyncSession(sync_engine) as session:
        incident = incident_service.run_detection(session, merchant_id)
        session.commit()

    if not incident:
        print("[demo] No incident detected yet — waiting more...")
        time.sleep(20)
        with SyncSession(sync_engine) as session:
            incident = incident_service.run_detection(session, merchant_id)
            session.commit()

    if not incident:
        print("[demo] Could not create incident. Check detection thresholds.")
        return

    incident_id = str(incident.id)
    print(f"[demo] Incident created: {incident_id}")

    # Step 4: Run investigation
    print("[demo] Step 4: AI investigation...")
    from backend.api.incidents import _sync_investigate
    _sync_investigate(incident_id, str(incident.merchant_id), incident.start_time)

    # Step 5: Auto-approve (demo mode)
    print("[demo] Step 5: Auto-approving recommendation...")
    with SyncSession(sync_engine) as session:
        rec = session.execute(
            text("SELECT id FROM recommendations WHERE incident_id = :id ORDER BY created_at DESC LIMIT 1"),
            {"id": incident_id}
        ).fetchone()
        if rec:
            incident_service.approve_recommendation(session, str(rec.id), "demo@paypulse.ai")
            session.commit()

    # Step 6: Execute action
    print("[demo] Step 6: Executing action...")
    with SyncSession(sync_engine) as session:
        rec = session.execute(
            text("SELECT id FROM recommendations WHERE incident_id = :id AND approval_status = 'APPROVED' ORDER BY created_at DESC LIMIT 1"),
            {"id": incident_id}
        ).fetchone()
        if rec:
            incident_service.execute_action(session, str(rec.id), "SYSTEM")
            session.commit()

    # Step 7: Switch to recovery
    print("[demo] Step 7: Recovery phase...")
    _sim_state["mode"] = "recovery"
    _sim_state["scenario"] = "recovery"
    time.sleep(30)

    # Step 8: Resolve
    print("[demo] Step 8: Resolving incident...")
    with SyncSession(sync_engine) as session:
        incident_service.resolve_incident(session, incident_id)
        session.commit()

    # Back to normal
    _sim_state["mode"] = "normal"
    _sim_state["scenario"] = None
    print(f"[demo] Demo complete! Incident {incident_id} resolved.")

import threading
