"""
PayPulse AI — Anomaly Detection Engine

Uses statistical methods (z-score, rolling deviation, baseline comparison)
to detect payment performance degradation. The LLM is never used for detection.
"""
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models import (
    IncidentSeverity, Transaction, PaymentMethod, Bank, Device, Location,
    HistoricalBaseline, Merchant
)


@dataclass
class AnomalySignal:
    dimension: str              # overall / payment_method / bank / device / location
    dimension_value: str        # UPI / HDFC / ANDROID / Mumbai / ALL
    current_rate: float
    baseline_rate: float
    deviation_pct: float        # positive = failure rate increase
    z_score: float
    transaction_count: int
    severity: IncidentSeverity
    is_anomalous: bool


@dataclass
class DetectionResult:
    is_anomalous: bool
    overall_severity: IncidentSeverity
    signals: list[AnomalySignal] = field(default_factory=list)
    current_success_rate: float = 0.0
    baseline_success_rate: float = 0.0
    affected_transaction_count: int = 0
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None


class AnomalyDetector:
    """
    Statistically detects payment anomalies using:
    1. Rolling window comparison against 7-day historical baseline
    2. Z-score calculation
    3. Percentage deviation thresholds
    4. Minimum volume guards to prevent false alarms
    """

    def __init__(self):
        self.zscore_threshold = settings.ANOMALY_ZSCORE_THRESHOLD
        self.pct_threshold = settings.ANOMALY_PCT_DEVIATION_THRESHOLD
        self.min_txns = settings.ANOMALY_MIN_TRANSACTIONS
        self.window_minutes = settings.ANOMALY_WINDOW_MINUTES

    def _compute_z_score(
        self, current_rate: float, baseline_rate: float, baseline_std: float, n: int
    ) -> float:
        """Compute z-score with sample-size correction."""
        if baseline_std == 0 or baseline_std is None:
            baseline_std = 0.05  # default std for bernoulli
        # Standard error of the mean
        se = baseline_std / math.sqrt(max(n, 1))
        if se == 0:
            return 0.0
        return (current_rate - baseline_rate) / se

    def _classify_severity(
        self, deviation_pct: float, z_score: float
    ) -> tuple[bool, IncidentSeverity]:
        """Map deviation metrics to severity level."""
        abs_dev = abs(deviation_pct)
        abs_z = abs(z_score)

        if abs_dev < self.pct_threshold or abs_z < self.zscore_threshold:
            return False, IncidentSeverity.LOW

        if abs_dev >= 40 or abs_z >= 6:
            return True, IncidentSeverity.CRITICAL
        elif abs_dev >= 25 or abs_z >= 4:
            return True, IncidentSeverity.HIGH
        elif abs_dev >= 15 or abs_z >= 2.5:
            return True, IncidentSeverity.MEDIUM
        else:
            return False, IncidentSeverity.LOW

    def _get_current_metrics(
        self,
        session: Session,
        merchant_id: str,
        window_start: datetime,
        window_end: datetime,
        dimension: str,
        dimension_value: Optional[str] = None,
    ) -> dict[str, tuple[int, int]]:
        """
        Returns dict of dimension_value -> (total_count, success_count)
        for the given time window.
        """
        if dimension == "overall":
            sql = text("""
                SELECT 'ALL' AS dim_val,
                       COUNT(*) AS total,
                       SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) AS successes
                FROM transactions
                WHERE merchant_id = :merchant_id
                  AND created_at BETWEEN :start AND :end
            """)
            rows = session.execute(sql, {
                "merchant_id": merchant_id,
                "start": window_start,
                "end": window_end,
            }).fetchall()
            return {r.dim_val: (int(r.total), int(r.successes or 0)) for r in rows}

        elif dimension == "payment_method":
            sql = text("""
                SELECT pm.type AS dim_val,
                       COUNT(*) AS total,
                       SUM(CASE WHEN t.status = 'SUCCESS' THEN 1 ELSE 0 END) AS successes
                FROM transactions t
                JOIN payment_methods pm ON t.payment_method_id = pm.id
                WHERE t.merchant_id = :merchant_id
                  AND t.created_at BETWEEN :start AND :end
                GROUP BY pm.type
            """)
        elif dimension == "bank":
            sql = text("""
                SELECT b.code AS dim_val,
                       COUNT(*) AS total,
                       SUM(CASE WHEN t.status = 'SUCCESS' THEN 1 ELSE 0 END) AS successes
                FROM transactions t
                JOIN banks b ON t.bank_id = b.id
                WHERE t.merchant_id = :merchant_id
                  AND t.created_at BETWEEN :start AND :end
                GROUP BY b.code
            """)
        elif dimension == "device":
            sql = text("""
                SELECT d.type AS dim_val,
                       COUNT(*) AS total,
                       SUM(CASE WHEN t.status = 'SUCCESS' THEN 1 ELSE 0 END) AS successes
                FROM transactions t
                JOIN devices d ON t.device_id = d.id
                WHERE t.merchant_id = :merchant_id
                  AND t.created_at BETWEEN :start AND :end
                GROUP BY d.type
            """)
        elif dimension == "location":
            sql = text("""
                SELECT l.city AS dim_val,
                       COUNT(*) AS total,
                       SUM(CASE WHEN t.status = 'SUCCESS' THEN 1 ELSE 0 END) AS successes
                FROM transactions t
                JOIN locations l ON t.location_id = l.id
                WHERE t.merchant_id = :merchant_id
                  AND t.created_at BETWEEN :start AND :end
                GROUP BY l.city
            """)
        else:
            return {}

        rows = session.execute(sql, {
            "merchant_id": merchant_id,
            "start": window_start,
            "end": window_end,
        }).fetchall()
        return {str(r.dim_val): (int(r.total), int(r.successes or 0)) for r in rows}

    def _get_baseline(
        self,
        session: Session,
        merchant_id: str,
        dimension: str,
        dimension_value: str,
    ) -> Optional[HistoricalBaseline]:
        return (
            session.query(HistoricalBaseline)
            .filter_by(
                merchant_id=merchant_id,
                dimension=dimension,
                dimension_value=dimension_value,
            )
            .first()
        )

    def analyze_dimension(
        self,
        session: Session,
        merchant_id: str,
        dimension: str,
        window_start: datetime,
        window_end: datetime,
    ) -> list[AnomalySignal]:
        """Analyze a single dimension for anomalies."""
        current_metrics = self._get_current_metrics(
            session, merchant_id, window_start, window_end, dimension
        )
        signals = []

        for dim_val, (total, successes) in current_metrics.items():
            if total < self.min_txns:
                continue

            current_rate = successes / total
            baseline = self._get_baseline(session, merchant_id, dimension, dim_val)

            if baseline is None:
                # No baseline → use a conservative default
                baseline_rate = 0.93
                baseline_std = 0.05
            else:
                baseline_rate = baseline.success_rate
                baseline_std = baseline.std_dev or 0.05

            deviation_pct = (baseline_rate - current_rate) / max(baseline_rate, 0.01) * 100
            z_score = self._compute_z_score(current_rate, baseline_rate, baseline_std, total)

            is_anomalous, severity = self._classify_severity(deviation_pct, z_score)

            signals.append(AnomalySignal(
                dimension=dimension,
                dimension_value=dim_val,
                current_rate=current_rate,
                baseline_rate=baseline_rate,
                deviation_pct=deviation_pct,
                z_score=z_score,
                transaction_count=total,
                severity=severity,
                is_anomalous=is_anomalous,
            ))

        return signals

    def detect(
        self,
        session: Session,
        merchant_id: str,
        window_minutes: Optional[int] = None,
    ) -> DetectionResult:
        """
        Main detection entry point.
        Analyzes all dimensions in the recent window.
        Returns structured DetectionResult.
        """
        window_minutes = window_minutes or self.window_minutes
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=window_minutes)

        all_signals: list[AnomalySignal] = []

        # Analyze all dimensions
        for dimension in ["overall", "payment_method", "bank", "device", "location"]:
            signals = self.analyze_dimension(
                session, merchant_id, dimension, window_start, now
            )
            all_signals.extend(signals)

        # Filter anomalous signals
        anomalous = [s for s in all_signals if s.is_anomalous]

        # Overall success rate
        overall_signal = next(
            (s for s in all_signals if s.dimension == "overall" and s.dimension_value == "ALL"),
            None,
        )
        current_rate = overall_signal.current_rate if overall_signal else 0.0
        baseline_rate = overall_signal.baseline_rate if overall_signal else 0.93

        # Count affected transactions in window
        count_sql = text("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) AS failures
            FROM transactions
            WHERE merchant_id = :merchant_id
              AND created_at BETWEEN :start AND :end
        """)
        count_row = session.execute(count_sql, {
            "merchant_id": merchant_id,
            "start": window_start,
            "end": now,
        }).fetchone()

        total_in_window = int(count_row.total or 0)
        failures_in_window = int(count_row.failures or 0)

        # Determine overall severity
        if not anomalous:
            overall_severity = IncidentSeverity.LOW
        else:
            # Take maximum severity across all anomalous signals
            severity_order = {
                IncidentSeverity.LOW: 0,
                IncidentSeverity.MEDIUM: 1,
                IncidentSeverity.HIGH: 2,
                IncidentSeverity.CRITICAL: 3,
            }
            overall_severity = max(anomalous, key=lambda s: severity_order[s.severity]).severity

        is_incident = (
            len(anomalous) > 0
            and overall_severity in (IncidentSeverity.MEDIUM, IncidentSeverity.HIGH, IncidentSeverity.CRITICAL)
        )

        return DetectionResult(
            is_anomalous=is_incident,
            overall_severity=overall_severity,
            signals=all_signals,
            current_success_rate=current_rate,
            baseline_success_rate=baseline_rate,
            affected_transaction_count=failures_in_window,
            window_start=window_start,
            window_end=now,
        )
