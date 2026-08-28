import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime, Enum as SAEnum,
    ForeignKey, Text, Numeric, Index, UniqueConstraint, JSON
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


def gen_uuid():
    return str(uuid.uuid4())


def now_utc():
    return datetime.now(timezone.utc)


# ─── Enumerations ─────────────────────────────────────────────────────────────

class PaymentMethodType(str, enum.Enum):
    UPI = "UPI"
    CARD = "CARD"
    NET_BANKING = "NET_BANKING"
    WALLET = "WALLET"
    EMI = "EMI"


class DeviceType(str, enum.Enum):
    ANDROID = "ANDROID"
    IOS = "IOS"
    DESKTOP = "DESKTOP"
    UNKNOWN = "UNKNOWN"


class TransactionStatus(str, enum.Enum):
    INITIATED = "INITIATED"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    RETRIED = "RETRIED"


class EventType(str, enum.Enum):
    PAYMENT_INITIATED = "PAYMENT_INITIATED"
    PAYMENT_PROCESSING = "PAYMENT_PROCESSING"
    PAYMENT_SUCCESS = "PAYMENT_SUCCESS"
    PAYMENT_FAILURE = "PAYMENT_FAILURE"
    PAYMENT_RETRY = "PAYMENT_RETRY"
    PAYMENT_REFUND = "PAYMENT_REFUND"
    TIMEOUT = "TIMEOUT"


class IncidentSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, enum.Enum):
    DETECTED = "DETECTED"
    INVESTIGATING = "INVESTIGATING"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    MITIGATING = "MITIGATING"
    MONITORING = "MONITORING"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


class ActionType(str, enum.Enum):
    NOTIFY_MERCHANT = "NOTIFY_MERCHANT"
    CREATE_SUPPORT_INCIDENT = "CREATE_SUPPORT_INCIDENT"
    RECOMMEND_ALTERNATIVE_PAYMENT_METHOD = "RECOMMEND_ALTERNATIVE_PAYMENT_METHOD"
    MONITOR_PAYMENT_HEALTH = "MONITOR_PAYMENT_HEALTH"
    ESCALATE_TO_PAYMENT_OPERATIONS = "ESCALATE_TO_PAYMENT_OPERATIONS"
    ENABLE_RETRY_LOGIC = "ENABLE_RETRY_LOGIC"
    ROUTE_TO_BACKUP_PROVIDER = "ROUTE_TO_BACKUP_PROVIDER"


class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"


class VerificationResult(str, enum.Enum):
    IMPROVED = "IMPROVED"
    PARTIALLY_IMPROVED = "PARTIALLY_IMPROVED"
    NO_IMPROVEMENT = "NO_IMPROVEMENT"
    WORSENED = "WORSENED"


# ─── Tables ───────────────────────────────────────────────────────────────────

class Merchant(Base):
    __tablename__ = "merchants"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    business_type = Column(String(100))
    razorpay_key_id = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    transactions = relationship("Transaction", back_populates="merchant")
    incidents = relationship("Incident", back_populates="merchant")


class Customer(Base):
    __tablename__ = "customers"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    merchant_id = Column(String(36), ForeignKey("merchants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255))
    phone = Column(String(20))
    segment = Column(String(50))  # NEW, RETURNING, VIP
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PaymentMethod(Base):
    __tablename__ = "payment_methods"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    name = Column(String(100), nullable=False)
    type = Column(SAEnum(PaymentMethodType), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Bank(Base):
    __tablename__ = "banks"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    code = Column(String(20), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Device(Base):
    __tablename__ = "devices"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    type = Column(SAEnum(DeviceType), nullable=False)
    os_version = Column(String(50))
    browser = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Location(Base):
    __tablename__ = "locations"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    country = Column(String(100), default="India")
    state = Column(String(100), nullable=False)
    city = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    merchant_id = Column(String(36), ForeignKey("merchants.id"), nullable=False)
    customer_id = Column(String(36), ForeignKey("customers.id"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default="INR")
    payment_method_id = Column(String(36), ForeignKey("payment_methods.id"))
    bank_id = Column(String(36), ForeignKey("banks.id"))
    device_id = Column(String(36), ForeignKey("devices.id"))
    location_id = Column(String(36), ForeignKey("locations.id"))
    status = Column(SAEnum(TransactionStatus), nullable=False)
    error_source = Column(String(100))   # BANK / GATEWAY / MERCHANT / CUSTOMER / NETWORK
    error_step = Column(String(100))     # INITIATION / AUTHENTICATION / AUTHORIZATION / SETTLEMENT
    error_reason = Column(String(255))   # e.g. INSUFFICIENT_FUNDS, TIMEOUT, DECLINED
    is_retry = Column(Boolean, default=False)
    retry_count = Column(Integer, default=0)
    scenario_tag = Column(String(50))    # for synthetic data labelling
    created_at = Column(DateTime(timezone=True), nullable=False)

    merchant = relationship("Merchant", back_populates="transactions")
    customer = relationship("Customer")
    payment_method = relationship("PaymentMethod")
    bank = relationship("Bank")
    device = relationship("Device")
    location = relationship("Location")
    events = relationship("PaymentEvent", back_populates="transaction")

    __table_args__ = (
        Index("ix_txn_merchant_created", "merchant_id", "created_at"),
        Index("ix_txn_status", "status"),
        Index("ix_txn_payment_method", "payment_method_id"),
        Index("ix_txn_bank", "bank_id"),
        Index("ix_txn_device", "device_id"),
        Index("ix_txn_created_at", "created_at"),
        Index("ix_txn_scenario", "scenario_tag"),
    )


class PaymentEvent(Base):
    __tablename__ = "payment_events"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    transaction_id = Column(String(36), ForeignKey("transactions.id"), nullable=False)
    event_type = Column(SAEnum(EventType), nullable=False)
    metadata_json = Column("metadata", JSON, default={})
    created_at = Column(DateTime(timezone=True), nullable=False)

    transaction = relationship("Transaction", back_populates="events")

    __table_args__ = (
        Index("ix_event_txn_id", "transaction_id"),
        Index("ix_event_created_at", "created_at"),
    )


class HistoricalBaseline(Base):
    __tablename__ = "historical_baselines"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    merchant_id = Column(String(36), ForeignKey("merchants.id"), nullable=False)
    dimension = Column(String(100), nullable=False)   # overall / payment_method / bank / device / location
    dimension_value = Column(String(255), nullable=False)   # UPI / HDFC / ANDROID / etc.
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    transaction_count = Column(Integer, nullable=False)
    success_count = Column(Integer, nullable=False)
    success_rate = Column(Float, nullable=False)
    avg_amount = Column(Numeric(12, 2))
    std_dev = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_baseline_merchant_dim", "merchant_id", "dimension", "dimension_value"),
        UniqueConstraint("merchant_id", "dimension", "dimension_value", "window_start", name="uq_baseline"),
    )


class IncidentType(Base):
    __tablename__ = "incident_types"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    default_severity = Column(SAEnum(IncidentSeverity), default=IncidentSeverity.MEDIUM)


class Incident(Base):
    __tablename__ = "incidents"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    merchant_id = Column(String(36), ForeignKey("merchants.id"), nullable=False)
    incident_type_id = Column(String(36), ForeignKey("incident_types.id"))
    severity = Column(SAEnum(IncidentSeverity), nullable=False)
    status = Column(SAEnum(IncidentStatus), nullable=False, default=IncidentStatus.DETECTED)
    title = Column(String(500))
    description = Column(Text)
    start_time = Column(DateTime(timezone=True), nullable=False)
    detected_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True))
    current_success_rate = Column(Float)
    baseline_success_rate = Column(Float)
    affected_transaction_count = Column(Integer, default=0)
    estimated_exposure = Column(Numeric(14, 2), default=0)
    investigation_report = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    merchant = relationship("Merchant", back_populates="incidents")
    signals = relationship("IncidentSignal", back_populates="incident")
    hypotheses = relationship("IncidentHypothesis", back_populates="incident")
    evidence_items = relationship("IncidentEvidence", back_populates="incident")
    recommendations = relationship("Recommendation", back_populates="incident")
    audit_logs = relationship("AuditLog", back_populates="incident")

    __table_args__ = (
        Index("ix_incident_merchant", "merchant_id"),
        Index("ix_incident_status", "status"),
        Index("ix_incident_severity", "severity"),
        Index("ix_incident_created", "created_at"),
    )


class IncidentSignal(Base):
    __tablename__ = "incident_signals"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=False)
    dimension = Column(String(100), nullable=False)
    dimension_value = Column(String(255))
    current_rate = Column(Float)
    baseline_rate = Column(Float)
    deviation_pct = Column(Float)
    z_score = Column(Float)
    transaction_count = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    incident = relationship("Incident", back_populates="signals")


class IncidentHypothesis(Base):
    __tablename__ = "incident_hypotheses"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    confidence = Column(Float)   # 0.0 to 1.0
    is_primary = Column(Boolean, default=False)
    supporting_evidence_ids = Column(JSON, default=[])
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    incident = relationship("Incident", back_populates="hypotheses")


class IncidentEvidence(Base):
    __tablename__ = "incident_evidence"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=False)
    evidence_type = Column(String(100), nullable=False)   # METRIC / EVENT / PATTERN / CORRELATION
    title = Column(String(500))
    description = Column(Text)
    data = Column(JSON)
    strength = Column(Float)   # 0.0 to 1.0
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    incident = relationship("Incident", back_populates="evidence_items")


class Recommendation(Base):
    __tablename__ = "recommendations"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=False)
    action_type = Column(SAEnum(ActionType), nullable=False)
    title = Column(String(500))
    description = Column(Text)
    reasoning = Column(Text)
    expected_improvement = Column(String(255))
    requires_approval = Column(Boolean, default=True)
    risk_level = Column(String(20), default="LOW")
    approval_status = Column(SAEnum(ApprovalStatus), default=ApprovalStatus.PENDING)
    approved_by = Column(String(255))
    approved_at = Column(DateTime(timezone=True))
    rejection_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    incident = relationship("Incident", back_populates="recommendations")
    action_results = relationship("ActionResult", back_populates="recommendation")


class ActionResult(Base):
    __tablename__ = "action_results"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    recommendation_id = Column(String(36), ForeignKey("recommendations.id"), nullable=False)
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=False)
    executed_at = Column(DateTime(timezone=True), server_default=func.now())
    executed_by = Column(String(255))
    success_rate_before = Column(Float)
    success_rate_after = Column(Float)
    absolute_improvement = Column(Float)
    pct_improvement = Column(Float)
    verification_result = Column(SAEnum(VerificationResult))
    verification_details = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    recommendation = relationship("Recommendation", back_populates="action_results")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    incident_id = Column(String(36), ForeignKey("incidents.id"))
    actor = Column(String(255), nullable=False)   # SYSTEM / merchant@email.com
    action = Column(String(255), nullable=False)
    reason = Column(Text)
    evidence_reference = Column(JSON)
    approval_status = Column(String(50))
    result = Column(String(255))
    metadata_json = Column("metadata", JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    incident = relationship("Incident", back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_incident", "incident_id"),
        Index("ix_audit_created", "created_at"),
    )
