"""
PayPulse AI — Synthetic Data Generator
Generates realistic payment transaction data with configurable scenarios.

Usage:
    py generate.py --mode normal --count 80000
    py generate.py --mode incident --scenario upi_degradation
    py generate.py --mode seed    (full demo seed)
"""
import sys
import os
import argparse
import random
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

# Add parent and current dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from faker import Faker
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.models import (
    Base, Merchant, Customer, PaymentMethod, Bank, Device, Location,
    Transaction, PaymentEvent, HistoricalBaseline, Incident, IncidentType,
    IncidentSignal, AuditLog,
    PaymentMethodType, DeviceType, TransactionStatus, EventType, IncidentSeverity, IncidentStatus
)
from backend.config import settings
from config import (
    BANKS, BANK_WEIGHTS, STATES_CITIES, LOCATION_WEIGHTS, DEVICE_WEIGHTS,
    PAYMENT_METHOD_WEIGHTS, AMOUNT_RANGES, ERROR_SOURCES, ERROR_STEPS,
    ERROR_REASONS, NORMAL_SUCCESS_RATE, CUSTOMER_SEGMENTS, SEGMENT_WEIGHTS,
    NUM_CUSTOMERS, SCENARIOS, DEFAULT_SEED
)

fake = Faker("en_IN")


from backend.database import sync_engine

class DataGenerator:
    def __init__(self, seed: int = DEFAULT_SEED):
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)
        fake.seed_instance(seed)
        self.engine = sync_engine

        # Will be populated during generate()
        self.merchant: Merchant | None = None
        self.customers: list[Customer] = []
        self.payment_methods: dict[str, PaymentMethod] = {}
        self.banks: dict[str, Bank] = {}
        self.devices: list[Device] = []
        self.locations: list[Location] = []

    def _setup_schema(self):
        Base.metadata.create_all(self.engine)
        print("[schema] Tables created/verified.")

    def _clear_data(self):
        with self.engine.begin() as conn:
            # Disable FK checks temporarily via CASCADE
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())
        print("[clear] All data cleared.")

    def _seed_static_entities(self, session: Session):
        """Seed merchant, payment methods, banks, devices, locations."""
        # Merchant
        merchant = Merchant(
            id=str(uuid.uuid4()),
            name="DemoMart Online",
            email="ops@demomart.com",
            business_type="E-Commerce",
            razorpay_key_id="rzp_test_demo",
        )
        session.add(merchant)
        self.merchant = merchant

        # Payment methods
        pm_defs = [
            ("UPI Payments", PaymentMethodType.UPI),
            ("Credit Card", PaymentMethodType.CARD),
            ("Debit Card", PaymentMethodType.CARD),
            ("Net Banking", PaymentMethodType.NET_BANKING),
            ("Paytm Wallet", PaymentMethodType.WALLET),
            ("EMI", PaymentMethodType.EMI),
        ]
        for name, pm_type in pm_defs:
            pm = PaymentMethod(id=str(uuid.uuid4()), name=name, type=pm_type)
            session.add(pm)
            self.payment_methods[pm_type.value] = pm  # map by type for easy access

        # Banks
        for (code, name), weight in zip(BANKS, BANK_WEIGHTS):
            bank = Bank(id=str(uuid.uuid4()), name=name, code=code)
            session.add(bank)
            self.banks[code] = bank

        # Devices
        for dtype, _ in DEVICE_WEIGHTS.items():
            for os_v, browser in [("Android 13", "Chrome"), ("Android 12", "Chrome"),
                                   ("iOS 17", "Safari"), ("iOS 16", "Safari"),
                                   ("Windows 11", "Chrome"), ("Windows 10", "Edge"),
                                   ("macOS 14", "Safari"), ("Unknown", "Unknown")]:
                d_type = DeviceType[dtype]
                device = Device(id=str(uuid.uuid4()), type=d_type, os_version=os_v, browser=browser)
                session.add(device)
                self.devices.append(device)

        # Locations
        for state, city in STATES_CITIES:
            loc = Location(id=str(uuid.uuid4()), state=state, city=city)
            session.add(loc)
            self.locations.append(loc)

        # Incident types
        incident_type_defs = [
            ("PAYMENT_METHOD_DEGRADATION", "Specific payment method experiencing higher failure rate"),
            ("BANK_DEGRADATION", "Specific bank experiencing connectivity or authorization issues"),
            ("DEVICE_DEGRADATION", "Specific device type experiencing disproportionate failures"),
            ("GEOGRAPHIC_DEGRADATION", "Geographic region experiencing network/connectivity issues"),
            ("MERCHANT_INTEGRATION_ISSUE", "Merchant-side integration or configuration causing failures"),
            ("OVERALL_DEGRADATION", "Platform-wide payment performance degradation"),
        ]
        for name, desc in incident_type_defs:
            it = IncidentType(id=str(uuid.uuid4()), name=name, description=desc)
            session.add(it)

        session.flush()
        print(f"[static] Merchant, {len(pm_defs)} PMs, {len(BANKS)} banks, {len(self.devices)} devices, {len(self.locations)} locations.")

    def _seed_customers(self, session: Session, count: int = NUM_CUSTOMERS):
        """Generate synthetic customers."""
        for _ in range(count):
            segment = random.choices(CUSTOMER_SEGMENTS, weights=SEGMENT_WEIGHTS)[0]
            cust = Customer(
                id=str(uuid.uuid4()),
                merchant_id=self.merchant.id,
                name=fake.name(),
                email=fake.email(),
                phone=fake.phone_number()[:20],
                segment=segment,
            )
            session.add(cust)
            self.customers.append(cust)
        session.flush()
        print(f"[customers] Generated {count} customers.")

    def _pick_payment_method(self) -> PaymentMethod:
        pm_type = random.choices(
            list(PAYMENT_METHOD_WEIGHTS.keys()),
            weights=list(PAYMENT_METHOD_WEIGHTS.values())
        )[0]
        return self.payment_methods[pm_type]

    def _pick_bank(self) -> Bank:
        code = random.choices([b[0] for b in BANKS], weights=BANK_WEIGHTS)[0]
        return self.banks[code]

    def _pick_device(self, device_type_name: str | None = None) -> Device:
        if device_type_name:
            matching = [d for d in self.devices if d.type.value == device_type_name]
            if matching:
                return random.choice(matching)
        dtype = random.choices(
            list(DEVICE_WEIGHTS.keys()),
            weights=list(DEVICE_WEIGHTS.values())
        )[0]
        matching = [d for d in self.devices if d.type.value == dtype]
        return random.choice(matching) if matching else random.choice(self.devices)

    def _pick_location(self, city_filter: str | None = None) -> Location:
        if city_filter:
            matching = [l for l in self.locations if l.city == city_filter]
            if matching:
                return random.choice(matching)
        idx = random.choices(range(len(self.locations)), weights=LOCATION_WEIGHTS)[0]
        return self.locations[idx]

    def _compute_success(
        self,
        pm_type: str,
        scenario: dict | None,
        txn_bank_code: str,
        txn_device_type: str,
        txn_city: str,
    ) -> bool:
        """Determine if a transaction succeeds based on scenario overrides."""
        if scenario is None:
            lo, hi = NORMAL_SUCCESS_RATE.get(pm_type, (0.90, 0.95))
            return random.random() < random.uniform(lo, hi)

        dim = scenario["affected_dimension"]
        val = scenario["affected_value"]
        lo, hi = scenario["success_rate_override"]

        # Check if this transaction falls in the affected segment
        affected = False
        if dim == "payment_method" and pm_type == val:
            affected = True
        elif dim == "bank" and txn_bank_code == val:
            affected = True
        elif dim == "device" and txn_device_type == val:
            affected = True
        elif dim == "location" and txn_city == val:
            affected = True
        elif dim == "overall":
            affected = True

        if affected:
            # Add noise so it's not a perfect cliff
            noise = random.gauss(0, 0.05)
            rate = max(0.10, min(0.99, random.uniform(lo, hi) + noise))
            return random.random() < rate
        else:
            lo2, hi2 = NORMAL_SUCCESS_RATE.get(pm_type, (0.90, 0.95))
            return random.random() < random.uniform(lo2, hi2)

    def _make_transaction(
        self,
        ts: datetime,
        scenario: dict | None = None,
        scenario_tag: str = "normal",
    ) -> tuple[Transaction, list[PaymentEvent]]:
        pm = self._pick_payment_method()
        bank = self._pick_bank()
        device = self._pick_device()
        location = self._pick_location()
        customer = random.choice(self.customers)

        pm_type = pm.type.value
        lo, hi = AMOUNT_RANGES.get(pm_type, (100, 10000))
        amount = round(random.uniform(lo, hi), 2)

        success = self._compute_success(
            pm_type, scenario, bank.code, device.type.value, location.city
        )

        status = TransactionStatus.SUCCESS if success else TransactionStatus.FAILED
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

        txn = Transaction(
            id=str(uuid.uuid4()),
            merchant_id=self.merchant.id,
            customer_id=customer.id,
            amount=Decimal(str(amount)),
            currency="INR",
            payment_method_id=pm.id,
            bank_id=bank.id,
            device_id=device.id,
            location_id=location.id,
            status=status,
            error_source=error_source,
            error_step=error_step,
            error_reason=error_reason,
            scenario_tag=scenario_tag,
            created_at=ts,
        )

        # Create payment events
        events = [
            PaymentEvent(
                id=str(uuid.uuid4()),
                transaction_id=txn.id,
                event_type=EventType.PAYMENT_INITIATED,
                created_at=ts,
            )
        ]
        proc_ts = ts + timedelta(seconds=random.uniform(0.5, 3))
        events.append(PaymentEvent(
            id=str(uuid.uuid4()),
            transaction_id=txn.id,
            event_type=EventType.PAYMENT_PROCESSING,
            created_at=proc_ts,
        ))
        final_ts = proc_ts + timedelta(seconds=random.uniform(1, 8))
        events.append(PaymentEvent(
            id=str(uuid.uuid4()),
            transaction_id=txn.id,
            event_type=EventType.PAYMENT_SUCCESS if success else EventType.PAYMENT_FAILURE,
            metadata={"error_reason": error_reason} if not success else {},
            created_at=final_ts,
        ))

        return txn, events

    def generate_normal_traffic(
        self,
        session: Session,
        count: int,
        start_time: datetime,
        end_time: datetime,
        batch_size: int = 1000,
    ):
        """Generate normal baseline transactions distributed over a time window."""
        total_seconds = (end_time - start_time).total_seconds()
        print(f"[normal] Generating {count:,} transactions from {start_time} to {end_time} ...")

        batch_txns = []
        batch_events = []

        for i in range(count):
            offset = random.uniform(0, total_seconds)
            # Add realistic diurnal pattern (more txns during business hours)
            hour = (start_time + timedelta(seconds=offset)).hour
            if hour < 6 or hour > 23:
                if random.random() < 0.7:
                    offset = random.uniform(
                        total_seconds * 0.4, total_seconds * 0.8
                    )
            ts = start_time + timedelta(seconds=offset)
            txn, evts = self._make_transaction(ts, scenario=None, scenario_tag="normal")
            batch_txns.append(txn)
            batch_events.extend(evts)

            if len(batch_txns) >= batch_size:
                session.bulk_save_objects(batch_txns)
                session.bulk_save_objects(batch_events)
                session.flush()
                batch_txns, batch_events = [], []
                print(f"  [{i+1:,}/{count:,}] flushed batch...")

        if batch_txns:
            session.bulk_save_objects(batch_txns)
            session.bulk_save_objects(batch_events)
            session.flush()

        print(f"[normal] Done.")

    def generate_incident_traffic(
        self,
        session: Session,
        scenario_name: str,
        count: int,
        incident_start: datetime,
        batch_size: int = 500,
    ) -> tuple[datetime, datetime]:
        """Generate transactions for a specific incident scenario."""
        scenario = SCENARIOS[scenario_name]
        duration = timedelta(minutes=scenario["duration_minutes"])
        incident_end = incident_start + duration

        print(f"[incident:{scenario_name}] Generating {count:,} transactions "
              f"from {incident_start} to {incident_end} ...")

        batch_txns = []
        batch_events = []

        for i in range(count):
            offset = random.uniform(0, duration.total_seconds())
            ts = incident_start + timedelta(seconds=offset)
            txn, evts = self._make_transaction(ts, scenario=scenario, scenario_tag=scenario_name)
            batch_txns.append(txn)
            batch_events.extend(evts)

            if len(batch_txns) >= batch_size:
                session.bulk_save_objects(batch_txns)
                session.bulk_save_objects(batch_events)
                session.flush()
                batch_txns, batch_events = [], []

        if batch_txns:
            session.bulk_save_objects(batch_txns)
            session.bulk_save_objects(batch_events)
            session.flush()

        print(f"[incident:{scenario_name}] Done. Window: {incident_start} — {incident_end}")
        return incident_start, incident_end

    def compute_baselines(self, session: Session):
        """Compute historical baselines from normal traffic."""
        print("[baselines] Computing historical baselines ...")
        merchant_id = self.merchant.id

        def to_dt(v):
            if isinstance(v, str):
                try:
                    return datetime.fromisoformat(v.replace("Z", "+00:00"))
                except Exception:
                    return datetime.now(timezone.utc)
            return v or datetime.now(timezone.utc)

        # 1. Overall baseline
        sql_overall = text("""
            SELECT
                status,
                CAST(amount AS FLOAT) as amount,
                created_at
            FROM transactions
            WHERE merchant_id = :merchant_id AND scenario_tag = 'normal'
        """)
        rows = session.execute(sql_overall, {"merchant_id": merchant_id}).fetchall()
        if rows:
            total = len(rows)
            successes = sum(1 for r in rows if r.status == "SUCCESS")
            rates = [1.0 if r.status == "SUCCESS" else 0.0 for r in rows]
            avg_amt = sum(r.amount for r in rows) / max(total, 1)
            mean_rate = successes / total
            std_dev = (sum((x - mean_rate) ** 2 for x in rates) / max(total - 1, 1)) ** 0.5

            b = HistoricalBaseline(
                id=str(uuid.uuid4()),
                merchant_id=merchant_id,
                dimension="overall",
                dimension_value="ALL",
                window_start=to_dt(rows[0].created_at),
                window_end=to_dt(rows[-1].created_at),
                transaction_count=total,
                success_count=successes,
                success_rate=mean_rate,
                avg_amount=Decimal(str(round(avg_amt, 2))),
                std_dev=round(std_dev, 4),
            )
            session.add(b)

        # 2. Dimensional baselines
        dimensions = [
            ("payment_method", "pm.type", "payment_methods pm ON t.payment_method_id = pm.id"),
            ("bank", "b.code", "banks b ON t.bank_id = b.id"),
            ("device", "d.type", "devices d ON t.device_id = d.id"),
            ("location", "l.city", "locations l ON t.location_id = l.id"),
        ]

        for dim_name, dim_col, join_clause in dimensions:
            sql = text(f"""
                SELECT
                    CAST({dim_col} AS TEXT) AS dim_val,
                    t.status,
                    CAST(t.amount AS FLOAT) as amount,
                    t.created_at
                FROM transactions t
                JOIN {join_clause}
                WHERE t.merchant_id = :merchant_id AND t.scenario_tag = 'normal'
            """)
            dim_rows = session.execute(sql, {"merchant_id": merchant_id}).fetchall()
            from collections import defaultdict
            grouped = defaultdict(list)
            for r in dim_rows:
                grouped[r.dim_val].append(r)

            for val, group in grouped.items():
                total = len(group)
                if total < 5:
                    continue
                successes = sum(1 for r in group if r.status == "SUCCESS")
                rates = [1.0 if r.status == "SUCCESS" else 0.0 for r in group]
                avg_amt = sum(r.amount for r in group) / total
                mean_rate = successes / total
                std_dev = (sum((x - mean_rate) ** 2 for x in rates) / max(total - 1, 1)) ** 0.5

                baseline = HistoricalBaseline(
                    id=str(uuid.uuid4()),
                    merchant_id=merchant_id,
                    dimension=dim_name,
                    dimension_value=str(val),
                    window_start=to_dt(group[0].created_at),
                    window_end=to_dt(group[-1].created_at),
                    transaction_count=total,
                    success_count=successes,
                    success_rate=mean_rate,
                    avg_amount=Decimal(str(round(avg_amt, 2))),
                    std_dev=round(std_dev, 4),
                )
                session.add(baseline)

        session.flush()
        print("[baselines] Done.")

    def full_demo_seed(self):
        """Complete seed: normal traffic + UPI incident scenario + recovery."""
        self._setup_schema()

        with Session(self.engine) as session:
            self._clear_data()
            self._seed_static_entities(session)
            self._seed_customers(session)

            # 7-day historical baseline (normal)
            now = datetime.now(timezone.utc)
            baseline_start = now - timedelta(days=8)
            baseline_end = now - timedelta(hours=2)

            self.generate_normal_traffic(
                session,
                count=80_000,
                start_time=baseline_start,
                end_time=baseline_end,
            )

            # 2 hours pre-incident normal traffic
            pre_incident_start = now - timedelta(hours=2)
            pre_incident_end = now - timedelta(minutes=50)
            self.generate_normal_traffic(
                session,
                count=500,
                start_time=pre_incident_start,
                end_time=pre_incident_end,
            )

            # UPI Degradation (40-50 minutes ago)
            incident_start = now - timedelta(minutes=50)
            self.generate_incident_traffic(
                session,
                scenario_name="upi_degradation",
                count=3_000,
                incident_start=incident_start,
            )

            # Recovery (20 minutes ago)
            recovery_start = now - timedelta(minutes=20)
            self.generate_incident_traffic(
                session,
                scenario_name="recovery",
                count=1_500,
                incident_start=recovery_start,
            )

            # Post-recovery normal (last 10 min)
            self.generate_normal_traffic(
                session,
                count=200,
                start_time=now - timedelta(minutes=10),
                end_time=now,
            )

            self.compute_baselines(session)
            session.commit()
            print("\n[seed] Full demo dataset ready!")
            print(f"[seed] Merchant: {self.merchant.name} ({self.merchant.id})")
            print(f"[seed] Customers: {len(self.customers)}")


def main():
    parser = argparse.ArgumentParser(description="PayPulse AI Data Generator")
    parser.add_argument("--mode", choices=["normal", "incident", "seed"], default="seed")
    parser.add_argument("--scenario", choices=list(SCENARIOS.keys()), default="upi_degradation")
    parser.add_argument("--count", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()

    gen = DataGenerator(seed=args.seed)

    if args.mode == "seed":
        gen.full_demo_seed()
    elif args.mode == "normal":
        gen._setup_schema()
        with Session(gen.engine) as session:
            gen._seed_static_entities(session)
            gen._seed_customers(session)
            now = datetime.now(timezone.utc)
            gen.generate_normal_traffic(session, args.count, now - timedelta(days=7), now)
            gen.compute_baselines(session)
            session.commit()
    elif args.mode == "incident":
        gen._setup_schema()
        with Session(gen.engine) as session:
            if not gen.customers:
                gen._seed_static_entities(session)
                gen._seed_customers(session)
                session.flush()
            now = datetime.now(timezone.utc)
            gen.generate_incident_traffic(
                session, args.scenario, args.count, now - timedelta(minutes=30)
            )
            session.commit()


if __name__ == "__main__":
    main()
