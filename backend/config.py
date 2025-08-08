# backend/config.py
from __future__ import annotations

from pathlib import Path
from typing import List, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Paths
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    # --- App meta (used by FastAPI docs and logging)
    APP_NAME: str = "Market Intel API"
    APP_VERSION: str = "0.1.0"

    # --- Server (used by __main__ in backend/app.py)
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = True

    # --- CORS
    # You can set ALLOWED_ORIGINS in .env as a comma-separated string or JSON list
    ALLOWED_ORIGINS: List[str] = ["*"]

    # --- External APIs
    FINNHUB_API_KEY: str = Field(min_length=1)

    # --- Requests / caching knobs (used by utils/)
    REQUEST_TIMEOUT_SECONDS: float = 10.0
    CACHE_TTL_SECONDS: int = 1800  # 30 minutes

    # --- NLP / Sentiment
    SENTIMENT_MODEL_ID: str = "ProsusAI/finbert"

    # --- News defaults
    NEWS_LOOKBACK_DAYS: int = 7
    NEWS_MAX_RESULTS: int = 50

    # --- Logging
    LOG_LEVEL: str = "INFO"

    # Pydantic settings
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(
        cls, v: Union[str, List[str]]
    ) -> List[str]:
        # Accept comma-separated env like: http://localhost:3000,http://localhost:5173
        if isinstance(v, str):
            items = [x.strip() for x in v.split(",") if x.strip()]
            return items or ["*"]
        return v


settings = Settings()
