# backend/app/services/market_data.py
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone, date as _date
from statistics import pstdev
from typing import Dict, List, Tuple

from app.core.config import settings
from app.logger import get_logger

# Primary (Finnhub)
from app.services.finance_data import (
    get_price as _get_price,
    get_historical_prices as _get_hist_finnhub,
    FinanceDataError,
)
def get_previous_close(ticker: str) -> float | None:
    t = (ticker or "").upper().strip()
    # 1) Yahoo fast_info
    try:
        import yfinance as yf
        tk = yf.Ticker(t)
        fi = getattr(tk, "fast_info", None)
        prev = None
        if fi is not None:
            prev = getattr(fi, "previous_close", None)
            if prev is None:
                prev = getattr(fi, "previousClose", None)
        if prev is not None:
            return float(prev)
    except Exception:
        pass
    # 2) Stooq
    try:
        end_dt = datetime.now(tz=timezone.utc)
        start_dt = end_dt - timedelta(days=10)
        if _get_hist_stooq:
            rows = _get_hist_stooq(t, start_date=start_dt, end_date=end_dt)
            if rows:
                rows.sort(key=lambda r: r["time"])
                return float(rows[-1]["close"])
    except Exception:
        pass
    # 3) Finnhub (if your plan allows candles)
    try:
        end_dt = datetime.now(tz=timezone.utc)
        start_dt = end_dt - timedelta(days=10)
        rows = _candles_from_finnhub(t, start_dt, end_dt)
        if rows:
            rows.sort(key=lambda r: r["time"])
            return float(rows[-1]["close"])
    except Exception:
        pass
    return None


# Yahoo fallback
try:
    from app.services.yahoo_data import get_historical_prices_yf as _get_hist_yahoo
except Exception:  # pragma: no cover
    _get_hist_yahoo = None

# Stooq fallback
try:
    from app.services.stooq_data import get_historical_prices_stooq as _get_hist_stooq
except Exception:  # pragma: no cover
    _get_hist_stooq = None

log = get_logger(__name__)

# ===================== CACHES =====================
_TTL = int(settings.CACHE_TTL_SECONDS or 600)

_cache_q: Dict[str, Tuple[float, float]] = {}                 # key -> (ts, price)
_cache_c: Dict[str, Tuple[float, List[float]]] = {}           # key -> (ts, closes)
_cache_chart: Dict[str, Tuple[float, Tuple[List[str], List[float], str]]] = {}


def _now() -> float:
    return time.time()


def _cache_get(store: Dict, key: str):
    it = store.get(key)
    if not it:
        return None
    ts, val = it
    if _now() - ts > _TTL:
        store.pop(key, None)
        return None
    return val


def _cache_put(store: Dict, key: str, val) -> None:
    store[key] = (_now(), val)


# ===================== PROVIDERS =====================

def _candles_from_finnhub(ticker: str, start_dt: datetime, end_dt: datetime) -> List[Dict]:
    return _get_hist_finnhub(ticker, start_date=start_dt, end_date=end_dt, resolution="D")


def _candles_from_yahoo(ticker: str, start_dt: datetime, end_dt: datetime) -> List[Dict]:
    if _get_hist_yahoo is None:
        return []
    return _get_hist_yahoo(ticker, start_date=start_dt, end_date=end_dt, interval="1d")


def _candles_from_stooq(ticker: str, start_dt: datetime, end_dt: datetime) -> List[Dict]:
    if _get_hist_stooq is None:
        return []
    return _get_hist_stooq(ticker, start_date=start_dt, end_date=end_dt)


def _provider_order() -> List[str]:
    pref = (settings.PREFERRED_PROVIDER or "auto").lower()
    if pref == "finnhub":
        return ["finnhub", "yahoo", "stooq"]
    if pref == "yahoo":
        return ["yahoo", "finnhub", "stooq"]
    if pref == "stooq":
        return ["stooq", "yahoo", "finnhub"]
    return ["finnhub", "yahoo", "stooq"]


# ===================== PUBLIC API =====================

def get_quote(ticker: str) -> float:
    """
    Latest price using Finnhub (cached briefly).
    Returns 0.0 on error (but logs why), so callers never crash.
    """
    key = f"q:{ticker.upper()}"
    cv = _cache_get(_cache_q, key)
    if cv is not None:
        return float(cv)

    try:
        p = float(_get_price(ticker))
        _cache_put(_cache_q, key, p)
        return p
    except FinanceDataError as e:
        log.error("quote failed for %s: %s", ticker, e)
        return 0.0


def get_candles_close(ticker: str, days: int = 60, resolution: str = "D") -> List[float]:
    """
    Daily closes for the last `days` with fallback:
    Finnhub → Yahoo → Stooq → synthetic.
    """
    if int(settings.DISABLE_CANDLES or 0) == 1:
        last = get_quote(ticker) or 100.0
        return [last] * max(2, int(days))

    days = max(1, int(days))
    key = f"c:{ticker.upper()}:{days}"
    cv = _cache_get(_cache_c, key)
    if cv is not None:
        return list(cv)

    end_dt = datetime.now(tz=timezone.utc)
    start_dt = end_dt - timedelta(days=days)

    for prov in _provider_order():
        try:
            if prov == "finnhub":
                rows = _candles_from_finnhub(ticker, start_dt, end_dt)
            elif prov == "yahoo":
                rows = _candles_from_yahoo(ticker, start_dt, end_dt)
            else:
                rows = _candles_from_stooq(ticker, start_dt, end_dt)

            closes = [float(r["close"]) for r in rows] if rows else []
            if closes:
                _cache_put(_cache_c, key, list(closes))
                log.info("candles provider=%s ticker=%s days=%d", prov, ticker, days)
                return closes
            else:
                log.warning("candles provider=%s returned no rows for %s", prov, ticker)
        except FinanceDataError as e:
            log.warning("candles provider=finnhub failed for %s: %s", ticker, e)
        except Exception as e:
            log.warning("candles provider=%s failed for %s: %s", prov, ticker, e)

    last = get_quote(ticker) or 100.0
    closes = [last] * max(2, days)
    _cache_put(_cache_c, key, list(closes))
    log.info("candles provider=synthetic ticker=%s days=%d", ticker, days)
    return closes


def compute_volatility(closes: List[float]) -> float:
    if not closes or len(closes) < 2:
        return 0.0
    clean = [c for c in closes if c and c > 0]
    if len(clean) < 2:
        return 0.0

    rets = []
    for i in range(1, len(clean)):
        p0, p1 = clean[i - 1], clean[i]
        if p0 <= 0:
            continue
        rets.append((p1 / p0) - 1.0)

    if len(rets) < 2:
        return 0.0

    daily_vol = pstdev(rets)
    return float(daily_vol * (252 ** 0.5))


def simple_trend_score(closes: List[float]) -> float:
    if len(closes) < 5:
        return 0.0
    n = min(20, len(closes))
    sma = sum(closes[-n:]) / n
    last = closes[-1]
    if sma <= 0:
        return 0.0
    raw = (last - sma) / sma
    return max(-1.0, min(1.0, raw))


def get_candles_rows_for_chart(ticker: str, days: int = 180) -> Tuple[List[str], List[float], str]:
    days = max(1, int(days))

    if int(settings.DISABLE_CANDLES or 0) == 1:
        last = get_quote(ticker) or 100.0
        closes = [last] * days
        end_dt = datetime.now(tz=timezone.utc)
        today = _date.fromtimestamp(int(end_dt.timestamp()))
        dates = [(today - timedelta(days=(days - 1 - i))).isoformat() for i in range(days)]
        return dates, closes, "synthetic"

    key = f"chart:{ticker.upper()}:{days}"
    cv = _cache_get(_cache_chart, key)
    if cv is not None:
        return cv

    end_dt = datetime.now(tz=timezone.utc)
    start_dt = end_dt - timedelta(days=days)

    for prov in _provider_order():
        try:
            if prov == "finnhub":
                rows = _candles_from_finnhub(ticker, start_dt, end_dt)
            elif prov == "yahoo":
                rows = _candles_from_yahoo(ticker, start_dt, end_dt)
            else:
                rows = _candles_from_stooq(ticker, start_dt, end_dt)

            if rows:
                rows.sort(key=lambda r: r["time"])
                dates = [r["time"].date().isoformat() for r in rows]
                closes = [float(r["close"]) for r in rows]
                val = (dates, closes, prov)
                _cache_put(_cache_chart, key, val)
                log.info("chart rows provider=%s ticker=%s days=%d", prov, ticker, days)
                return val
            else:
                log.warning("chart rows provider=%s returned no rows for %s", prov, ticker)
        except FinanceDataError as e:
            log.warning("chart rows provider=finnhub failed for %s: %s", ticker, e)
        except Exception as e:
            log.warning("chart rows provider=%s failed for %s: %s", prov, ticker, e)

    last = get_quote(ticker) or 100.0
    closes = [last] * days
    today = _date.fromtimestamp(int(end_dt.timestamp()))
    dates = [(today - timedelta(days=(days - 1 - i))).isoformat() for i in range(days)]
    val = (dates, closes, "synthetic")
    _cache_put(_cache_chart, key, val)
    log.info("chart rows provider=synthetic ticker=%s days=%d", ticker, days)
    return val


# ===== Debug helpers =====

def _has_yahoo() -> bool:
    return _get_hist_yahoo is not None

def _has_stooq() -> bool:
    return _get_hist_stooq is not None

def debug_status() -> dict:
    return {
        "DISABLE_CANDLES": settings.DISABLE_CANDLES,
        "PREFERRED_PROVIDER": settings.PREFERRED_PROVIDER,
        "CACHE_TTL_SECONDS": settings.CACHE_TTL_SECONDS,
        "provider_order": _provider_order(),
        "yahoo_available": _has_yahoo(),
        "stooq_available": _has_stooq(),
        "cache_sizes": {
            "quotes": len(_cache_q),
            "candles": len(_cache_c),
            "chart": len(_cache_chart),
        },
    }

def debug_clear_cache() -> dict:
    q, c, ch = len(_cache_q), len(_cache_c), len(_cache_chart)
    _cache_q.clear(); _cache_c.clear(); _cache_chart.clear()
    return {"cleared": {"quotes": q, "candles": c, "chart": ch}}
 # === New helper: previous close (no synthetic), with robust fallbacks ========

