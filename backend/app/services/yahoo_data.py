# backend/app/services/yahoo_data.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
import time
import yfinance as yf

def _with_retries(fn, attempts=3, delay=1.0):
    last_err = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            last_err = e
            if i < attempts - 1:
                time.sleep(delay)
    if last_err:
        raise last_err

def _to_dt_utc(x: Optional[Union[str, datetime]]) -> Optional[datetime]:
    if x is None:
        return None
    if isinstance(x, datetime):
        return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
    if isinstance(x, str):
        dt = datetime.fromisoformat(x)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None

def _df_to_rows(df) -> List[Dict[str, Any]]:
    if df is None or getattr(df, "empty", True):
        return []
    # history() may return a "Period" index or DatetimeIndex; normalize
    if "Open" not in df.columns or "Close" not in df.columns:
        return []
    df = df.dropna()
    out: List[Dict[str, Any]] = []
    for ts, row in df.iterrows():
        # ts can be pandas.Timestamp or Period
        t = getattr(ts, "to_timestamp", lambda: ts)()
        t = t.to_pydatetime()
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        else:
            t = t.astimezone(timezone.utc)
        try:
            out.append({
                "time": t,
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low":  float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row.get("Volume", 0) or 0),
            })
        except Exception:
            # Skip malformed rows instead of raising
            continue
    return out

def get_historical_prices_yf(
    ticker: str,
    start_date: Optional[Union[str, datetime]] = None,
    end_date: Optional[Union[str, datetime]] = None,
    interval: str = "1d",
    proxy: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Robust Yahoo Finance fallback:
      1) Try yf.download()
      2) If empty, try Ticker().history()
      Returns rows (time, open, high, low, close, volume) in UTC.
    """
    t = ticker.strip().upper()
    sd = _to_dt_utc(start_date)
    ed = _to_dt_utc(end_date)

    def _try_download():
        return yf.download(
            t, start=sd, end=ed, interval=interval,
            auto_adjust=False, progress=False, threads=False, proxy=proxy,
        )

    try:
        df = _with_retries(_try_download, attempts=2, delay=0.8)
        rows = _df_to_rows(df)
        if rows:
            return rows
    except Exception:
        pass

    def _try_history():
        tk = yf.Ticker(t, proxy=proxy)
        if sd is None or ed is None:
            return tk.history(period="6mo", interval=interval, auto_adjust=False)
        return tk.history(start=sd, end=ed, interval=interval, auto_adjust=False)

    df2 = _with_retries(_try_history, attempts=2, delay=0.8)
    return _df_to_rows(df2)
