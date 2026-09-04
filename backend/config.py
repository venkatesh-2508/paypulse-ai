import os
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres.lfdyxolherrsbkoakfxz:paypulse%407671@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres"
    DATABASE_URL_SYNC: str = "postgresql://postgres.lfdyxolherrsbkoakfxz:paypulse%407671@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres"

    # AI
    GEMINI_API_KEY: Optional[str] = None

    # App
    APP_NAME: str = "PayPulse AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    CORS_ORIGINS: str = "http://localhost:3000"

    # Detection thresholds
    ANOMALY_ZSCORE_THRESHOLD: float = 2.5
    ANOMALY_PCT_DEVIATION_THRESHOLD: float = 15.0
    ANOMALY_MIN_TRANSACTIONS: int = 20
    ANOMALY_WINDOW_MINUTES: int = 30
    BASELINE_DAYS: int = 7

    # Simulator
    SIM_NORMAL_SUCCESS_RATE_MIN: float = 0.92
    SIM_NORMAL_SUCCESS_RATE_MAX: float = 0.96
    SIM_TPS: float = 2.0  # transactions per second for live sim

    model_config = {
        "env_file": [
            os.path.join(os.path.dirname(__file__), ".env"),
            os.path.join(os.path.dirname(__file__), "..", ".env"),
            ".env"
        ],
        "extra": "ignore"
    }

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]


settings = Settings()
