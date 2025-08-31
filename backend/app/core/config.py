# backend/app/core/config.py
from __future__ import annotations
import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

# 👇 This resolves to <repo-root>/backend/.env when this file is at backend/app/core/config.py
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"  # <-- FIXED: no extra "backend"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),      # use the file above
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- your existing fields below (unchanged) ---
    MONGO_URI: str = "mongodb://127.0.0.1:27017"
    MONGO_DB_NAME: str = "ai_invest"
    ENV: str = "development"
    API_PREFIX: str = "/api"
    CORS_ORIGINS: List[str] = []
    ALLOWED_ORIGINS: Optional[str] = None
    SECRET_KEY: str = "dev"
    DATABASE_URL: str = "sqlite:///./dev.db"
    FINBERT_MODEL: str = "ProsusAI/finbert"
    FINNHUB_API_KEY: Optional[str] = None
    LOG_LEVEL: str = "INFO"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = False
    WATCH_TICKERS: List[str] = ["AAPL", "MSFT", "TSLA"]
    SCHEDULE_MINUTES: int = 30
    DISABLE_CANDLES: int = 0
    PREFERRED_PROVIDER: str = "auto"
    CACHE_TTL_SECONDS: int = 600
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_WHATSAPP_FROM: Optional[str] = None
    WHATSAPP_TO: Optional[str] = None
    TWILIO_CONTENT_SID: Optional[str] = None

    # Enhanced sentiment analysis settings (optional additions)
    SENTIMENT_CONFIDENCE_THRESHOLD: float = 0.7  # Threshold for high confidence alerts
    SENTIMENT_CHANGE_THRESHOLD: float = 0.2      # Threshold for significant sentiment changes
    MAX_SENTIMENT_CACHE_SIZE: int = 1000         # Cache size for sentiment results
    SENTIMENT_BATCH_SIZE: int = 32               # Batch size for efficient processing
    
    # Enhanced WhatsApp settings (optional additions)
    WHATSAPP_SESSION_WARNING_HOURS: int = 1     # Hours before expiry to send warning
    DAILY_DIGEST_HOUR: int = 8                  # Hour to send daily digest (IST)
    ENABLE_SENTIMENT_ALERTS: bool = True        # Enable/disable sentiment change alerts
    
    # News analysis settings (optional additions)  
    MAX_NEWS_ARTICLES: int = 30                 # Max articles per ticker for analysis
    NEWS_LOOKBACK_HOURS: int = 24               # How far back to look for news

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors(cls, v):
        if isinstance(v, list):
            return v
        raw = v or os.getenv("ALLOWED_ORIGINS", "")
        return [o.strip() for o in str(raw).split(",") if o.strip()]

    @field_validator("WATCH_TICKERS", mode="before")
    @classmethod
    def _parse_watch_tickers(cls, v):
        if isinstance(v, list):
            return [t.strip().upper() for t in v]
        raw = str(v or "AAPL,MSFT,TSLA")
        return [t.strip().upper() for t in raw.split(",") if t.strip()]

    @field_validator("RELOAD", mode="before")
    @classmethod
    def _parse_reload_bool(cls, v):
        if isinstance(v, bool):
            return v
        return str(v).lower() in ("1", "true", "yes", "on")

    @field_validator("ENABLE_SENTIMENT_ALERTS", mode="before")
    @classmethod
    def _parse_sentiment_alerts_bool(cls, v):
        if isinstance(v, bool):
            return v
        return str(v).lower() in ("1", "true", "yes", "on")

    # Validation for confidence threshold
    @field_validator("SENTIMENT_CONFIDENCE_THRESHOLD")
    @classmethod
    def _validate_confidence_threshold(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("SENTIMENT_CONFIDENCE_THRESHOLD must be between 0.0 and 1.0")
        return v

    # Validation for change threshold
    @field_validator("SENTIMENT_CHANGE_THRESHOLD")
    @classmethod
    def _validate_change_threshold(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("SENTIMENT_CHANGE_THRESHOLD must be between 0.0 and 1.0")
        return v

    # Validation for daily digest hour
    @field_validator("DAILY_DIGEST_HOUR")
    @classmethod
    def _validate_digest_hour(cls, v):
        if not 0 <= v <= 23:
            raise ValueError("DAILY_DIGEST_HOUR must be between 0 and 23")
        return v

settings = Settings()