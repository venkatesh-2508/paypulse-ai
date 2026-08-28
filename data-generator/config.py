"""
PayPulse AI — Synthetic Data Generator Configuration
"""
import random

# ─── Random seed control ──────────────────────────────────────────────────────
DEFAULT_SEED = 42

# ─── Data volume ──────────────────────────────────────────────────────────────
NUM_CUSTOMERS = 5_000
NUM_TRANSACTIONS_NORMAL = 80_000   # historical baseline period
NUM_TRANSACTIONS_INCIDENT = 8_000  # incident window

# ─── Normal traffic parameters ────────────────────────────────────────────────
NORMAL_SUCCESS_RATE = {
    "UPI": (0.93, 0.96),
    "CARD": (0.91, 0.95),
    "NET_BANKING": (0.88, 0.93),
    "WALLET": (0.94, 0.97),
    "EMI": (0.89, 0.93),
}

# Weighted payment method distribution (realistic India market share)
PAYMENT_METHOD_WEIGHTS = {
    "UPI": 0.52,
    "CARD": 0.22,
    "NET_BANKING": 0.10,
    "WALLET": 0.10,
    "EMI": 0.06,
}

BANKS = [
    ("HDFC", "HDFC Bank"),
    ("ICICI", "ICICI Bank"),
    ("SBI", "State Bank of India"),
    ("AXIS", "Axis Bank"),
    ("KOTAK", "Kotak Mahindra Bank"),
    ("YES", "Yes Bank"),
    ("PNB", "Punjab National Bank"),
    ("BOI", "Bank of India"),
    ("CANARA", "Canara Bank"),
    ("INDUS", "IndusInd Bank"),
]

BANK_WEIGHTS = [0.22, 0.18, 0.20, 0.12, 0.08, 0.05, 0.06, 0.04, 0.03, 0.02]

STATES_CITIES = [
    ("Maharashtra", "Mumbai"),
    ("Maharashtra", "Pune"),
    ("Karnataka", "Bengaluru"),
    ("Tamil Nadu", "Chennai"),
    ("Delhi", "New Delhi"),
    ("Telangana", "Hyderabad"),
    ("Gujarat", "Ahmedabad"),
    ("West Bengal", "Kolkata"),
    ("Rajasthan", "Jaipur"),
    ("Uttar Pradesh", "Lucknow"),
]

LOCATION_WEIGHTS = [0.18, 0.09, 0.16, 0.10, 0.14, 0.09, 0.07, 0.06, 0.06, 0.05]

DEVICE_WEIGHTS = {
    "ANDROID": 0.58,
    "IOS": 0.22,
    "DESKTOP": 0.18,
    "UNKNOWN": 0.02,
}

AMOUNT_RANGES = {
    "UPI": (50, 5000),
    "CARD": (200, 25000),
    "NET_BANKING": (500, 100000),
    "WALLET": (50, 2000),
    "EMI": (5000, 150000),
}

ERROR_SOURCES = ["BANK", "GATEWAY", "MERCHANT", "CUSTOMER", "NETWORK"]
ERROR_STEPS = ["INITIATION", "AUTHENTICATION", "AUTHORIZATION", "SETTLEMENT"]
ERROR_REASONS = [
    "INSUFFICIENT_FUNDS",
    "TIMEOUT",
    "DECLINED_BY_BANK",
    "INVALID_OTP",
    "NETWORK_ERROR",
    "DUPLICATE_REQUEST",
    "LIMIT_EXCEEDED",
    "TECHNICAL_ERROR",
    "VPA_NOT_FOUND",
    "DEBIT_FAILED",
]

# ─── Scenario parameters ──────────────────────────────────────────────────────
SCENARIOS = {
    "upi_degradation": {
        "description": "UPI payment method experiences significant degradation",
        "affected_dimension": "payment_method",
        "affected_value": "UPI",
        "success_rate_override": (0.55, 0.68),
        "error_reason_concentration": "TIMEOUT",
        "error_source_concentration": "BANK",
        "duration_minutes": 45,
    },
    "bank_degradation": {
        "description": "Specific bank (HDFC) experiences degradation",
        "affected_dimension": "bank",
        "affected_value": "HDFC",
        "success_rate_override": (0.45, 0.60),
        "error_reason_concentration": "TECHNICAL_ERROR",
        "error_source_concentration": "BANK",
        "duration_minutes": 30,
    },
    "device_degradation": {
        "description": "Android devices experience degradation",
        "affected_dimension": "device",
        "affected_value": "ANDROID",
        "success_rate_override": (0.65, 0.75),
        "error_reason_concentration": "TIMEOUT",
        "error_source_concentration": "GATEWAY",
        "duration_minutes": 60,
    },
    "geo_degradation": {
        "description": "Geographic degradation affecting Mumbai transactions",
        "affected_dimension": "location",
        "affected_value": "Mumbai",
        "success_rate_override": (0.60, 0.72),
        "error_reason_concentration": "NETWORK_ERROR",
        "error_source_concentration": "NETWORK",
        "duration_minutes": 25,
    },
    "merchant_integration": {
        "description": "Merchant integration issue causing widespread failures",
        "affected_dimension": "overall",
        "affected_value": "ALL",
        "success_rate_override": (0.50, 0.65),
        "error_reason_concentration": "TECHNICAL_ERROR",
        "error_source_concentration": "MERCHANT",
        "duration_minutes": 20,
    },
    "temporary_fluctuation": {
        "description": "Brief random fluctuation — should NOT trigger incident",
        "affected_dimension": "overall",
        "affected_value": "ALL",
        "success_rate_override": (0.86, 0.90),  # mild dip, within tolerance
        "error_reason_concentration": None,
        "error_source_concentration": None,
        "duration_minutes": 5,
    },
    "recovery": {
        "description": "Traffic recovers after simulated intervention",
        "affected_dimension": "payment_method",
        "affected_value": "UPI",
        "success_rate_override": (0.90, 0.95),  # recovery to near-normal
        "error_reason_concentration": None,
        "error_source_concentration": None,
        "duration_minutes": 30,
    },
}

CUSTOMER_SEGMENTS = ["NEW", "RETURNING", "VIP"]
SEGMENT_WEIGHTS = [0.30, 0.55, 0.15]
