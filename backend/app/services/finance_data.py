# backend/app/services/finance_data.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Union
import requests

from app.core.config import settings


class FinanceDataError(Exception):
    """Raised when a provider (Finnhub) can't return data properly."""


def _ensure_api_key() -> str:
    key = settings.FINNHUB_API_KEY or ""
    if not key:
        raise FinanceDataError(
            "FINNHUB_API_KEY is missing. Put it in backend/.env as FINNHUB_API_KEY=..."
        )
    return key


def _to_ts_utc(d: Optional[Union[str, datetime]]) -> Optional[int]:
    if d is None:
        return None
    if isinstance(d, datetime):
        dt = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    if isinstance(d, str):
        dt = datetime.fromisoformat(d)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    raise FinanceDataError(f"Invalid date value: {d!r}")


def get_price(ticker: str) -> float:
    """
    Return latest price from Finnhub /quote.
    Raises FinanceDataError on provider/config errors.
    """
    key = _ensure_api_key()
    url = "https://finnhub.io/api/v1/quote"
    params = {"symbol": ticker.upper(), "token": key}

    try:
        r = requests.get(url, params=params, timeout=8)
        if r.status_code in (401, 403):
            raise FinanceDataError(f"Finnhub denied access ({r.status_code}).")
        r.raise_for_status()
        data = r.json()
    except FinanceDataError:
        raise
    except Exception as e:
        raise FinanceDataError(f"Finnhub quote failed: {e}")

    c = data.get("c")
    if c is None:
        raise FinanceDataError("Finnhub quote missing field 'c'")
    return float(c)


def get_historical_prices(
    ticker: str,
    *,
    start_date: Optional[Union[str, datetime]] = None,
    end_date: Optional[Union[str, datetime]] = None,
    resolution: str = "D",  # '1','5','15','30','60','D','W','M'
) -> List[Dict]:
    """
    Return OHLCV rows from Finnhub /stock/candle.
    Each row: {time: datetime(UTC), open, high, low, close, volume}
    Raises FinanceDataError on provider/config errors.
    """
    key = _ensure_api_key()

    res_map = {"D": "D", "W": "W", "M": "M", "60": "60", "30": "30", "15": "15", "5": "5", "1": "1"}
    res = res_map.get(str(resolution).upper(), "D")

    to_ts = _to_ts_utc(end_date) or int(datetime.now(tz=timezone.utc).timestamp())
    default_span = 120 * 24 * 3600 if res == "D" else 30 * 24 * 3600
    frm_ts = _to_ts_utc(start_date) or (to_ts - default_span)

    url = "https://finnhub.io/api/v1/stock/candle"
    params = {"symbol": ticker.upper(), "resolution": res, "from": frm_ts, "to": to_ts, "token": key}

    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code in (401, 403):
            raise FinanceDataError(f"Finnhub denied access ({r.status_code}).")
        r.raise_for_status()
        data = r.json()
    except FinanceDataError:
        raise
    except Exception as e:
        raise FinanceDataError(f"Finnhub candles failed: {e}")

    if data.get("s") != "ok":
        raise FinanceDataError(f"Finnhub returned status {data.get('s')!r}")

    out: List[Dict] = []
    t_arr = data.get("t", []) or []
    o_arr = data.get("o", []) or []
    h_arr = data.get("h", []) or []
    l_arr = data.get("l", []) or []
    c_arr = data.get("c", []) or []
    v_arr = data.get("v", []) or []

    for i, ts in enumerate(t_arr):
        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        out.append(
            {
                "time": dt,
                "open": float(o_arr[i]),
                "high": float(h_arr[i]),
                "low": float(l_arr[i]),
                "close": float(c_arr[i]),
                "volume": int(v_arr[i]) if i < len(v_arr) and v_arr[i] is not None else 0,
            }
        )
    return out
