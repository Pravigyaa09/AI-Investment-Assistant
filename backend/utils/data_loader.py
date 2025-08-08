# backend/utils/data_loader.py
from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, Callable
import pandas as pd
import yfinance as yf

from logger import get_logger

logger = get_logger(__name__)


# -----------------------------
# Tiny in-memory TTL cache
# -----------------------------
class _TTLCache:
    def __init__(self, ttl_seconds: int = 300, maxsize: int = 128):
        self.ttl = ttl_seconds
        self.maxsize = maxsize
        self._data: Dict[Tuple, Tuple[float, Any]] = {}

    def get(self, key: Tuple):
        now = time.time()
        item = self._data.get(key)
        if not item:
            return None
        ts, val = item
        if now - ts > self.ttl:
            self._data.pop(key, None)
            return None
        return val

    def set(self, key: Tuple, value: Any):
        if len(self._data) >= self.maxsize:
            # Drop oldest-ish (naive; good enough here)
            oldest_key = next(iter(self._data))
            self._data.pop(oldest_key, None)
        self._data[key] = (time.time(), value)


def ttl_cached(ttl_seconds: int = 300, maxsize: int = 128):
    cache = _TTLCache(ttl_seconds, maxsize)

    def decorator(fn: Callable):
        def wrapper(*args, **kwargs):
            key = (fn.__name__, args, tuple(sorted(kwargs.items())))
            val = cache.get(key)
            if val is not None:
                return val
            val = fn(*args, **kwargs)
            cache.set(key, val)
            return val
        return wrapper
    return decorator


# -----------------------------
# Helpers
# -----------------------------
def _sanitize_ticker(ticker: str) -> str:
    if not isinstance(ticker, str):
        raise ValueError("Ticker must be a string")
    t = ticker.strip().upper()
    if not t:
        raise ValueError("Ticker is empty")
    return t


def _normalize_history(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure consistent columns & UTC index."""
    if df is None or df.empty:
        return pd.DataFrame()

    # Some yfinance versions return "Adj Close"
    if "Adj Close" in df.columns and "AdjClose" not in df.columns:
        df = df.rename(columns={"Adj Close": "AdjClose"})

    # Ensure datetime index in UTC (if it has tz, convert; else localize then convert)
    if isinstance(df.index, pd.DatetimeIndex):
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")
    else:
        df.index = pd.to_datetime(df.index, utc=True)

    # for JSON friendliness
    df = df.copy()
    df["Date"] = df.index.tz_convert("UTC").to_pydatetime()
    return df


# -----------------------------
# Public API
# -----------------------------
@ttl_cached(ttl_seconds=180, maxsize=256)
def fetch_price_history(
    ticker: str,
    *,
    start: Optional[str | datetime] = None,
    end: Optional[str | datetime] = None,
    period: str = "1y",
    interval: str = "1d",
    auto_adjust: bool = True,
    prepost: bool = False,
) -> pd.DataFrame:
    """
    Fetch EOD/interval OHLCV from yfinance. Returns normalized DataFrame.
    You can specify either (start/end) or a period like '1y', '6mo', etc.
    """
    t = _sanitize_ticker(ticker)
    logger.info("Fetching price history: ticker=%s period=%s interval=%s", t, period, interval)

    try:
        tk = yf.Ticker(t)
        if start or end:
            df = tk.history(
                start=start,
                end=end,
                interval=interval,
                auto_adjust=auto_adjust,
                prepost=prepost,
            )
        else:
            df = tk.history(
                period=period,
                interval=interval,
                auto_adjust=auto_adjust,
                prepost=prepost,
            )
        df = _normalize_history(df)
        logger.info("Fetched %d rows for %s", len(df), t)
        return df
    except Exception as e:
        logger.exception("Failed to fetch history for %s: %s", t, e)
        return pd.DataFrame()


@ttl_cached(ttl_seconds=90, maxsize=256)
def fetch_intraday(
    ticker: str,
    *,
    period: str = "5d",
    interval: str = "5m",
    auto_adjust: bool = True,
    prepost: bool = False,
) -> pd.DataFrame:
    """
    Fetch intraday OHLCV (e.g., 1m/5m/15m). yfinance caps period based on interval.
    """
    return fetch_price_history(
        ticker,
        period=period,
        interval=interval,
        auto_adjust=auto_adjust,
        prepost=prepost,
    )


@ttl_cached(ttl_seconds=30, maxsize=512)
def fetch_latest_price(ticker: str) -> Optional[float]:
    """
    Get a best-effort latest price. Tries fast_info; falls back to last close.
    """
    t = _sanitize_ticker(ticker)
    try:
        tk = yf.Ticker(t)
        # Fast path
        fi = getattr(tk, "fast_info", None)
        if fi and isinstance(fi, dict):
            last = fi.get("last_price") or fi.get("lastPrice") or fi.get("last")
            if last:
                return float(last)

        # Fallback: last close from short intraday
        df = tk.history(period="1d", interval="1m", auto_adjust=True, prepost=True)
        if not df.empty:
            return float(df["Close"].iloc[-1])
    except Exception as e:
        logger.exception("Failed to fetch latest price for %s: %s", t, e)
    return None


@ttl_cached(ttl_seconds=600, maxsize=256)
def fetch_company_profile(ticker: str) -> Dict[str, Any]:
    """
    Return a small, stable subset of company info fields.
    """
    t = _sanitize_ticker(ticker)
    logger.info("Fetching company profile for %s", t)
    try:
        tk = yf.Ticker(t)
        info = getattr(tk, "info", {}) or {}
        fast = getattr(tk, "fast_info", {}) or {}

        # Pick safe keys (yfinance's .info can vary wildly)
        profile = {
            "symbol": t,
            "shortName": info.get("shortName") or info.get("longName"),
            "longName": info.get("longName") or info.get("shortName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "country": info.get("country"),
            "website": info.get("website"),
            "currency": info.get("currency") or fast.get("currency"),
            "marketCap": info.get("marketCap"),
            "sharesOutstanding": info.get("sharesOutstanding"),
            "beta": info.get("beta"),
            "forwardPE": info.get("forwardPE"),
            "trailingPE": info.get("trailingPE"),
        }
        return {k: v for k, v in profile.items() if v is not None}
    except Exception as e:
        logger.exception("Failed to fetch profile for %s: %s", t, e)
        return {"symbol": t, "error": "profile_unavailable"}


def add_returns(
    df: pd.DataFrame,
    windows: tuple[int, ...] = (1, 5, 20),
    price_col: str = "Close",
) -> pd.DataFrame:
    """
    Add % returns columns (r_1, r_5, ...) to a price history DataFrame.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    if price_col not in df.columns:
        raise ValueError(f"Expected column '{price_col}' not found.")

    out = df.copy()
    for w in windows:
        out[f"r_{w}"] = out[price_col].pct_change(w)
    return out


def to_json_records(df: pd.DataFrame, limit: Optional[int] = None) -> list[dict]:
    """
    Convert a (possibly large) DataFrame to JSON-serializable list of dicts.
    """
    if df is None or df.empty:
        return []
    slim = df.tail(limit) if limit else df
    # Make datetimes ISO strings
    if "Date" in slim.columns:
        slim = slim.copy()
        slim["Date"] = pd.to_datetime(slim["Date"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return slim.reset_index(drop=True).to_dict(orient="records")
