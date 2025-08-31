# backend/app/services/stooq_data.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from pandas_datareader import data as pdr
import pandas as pd

def _to_date(x: Optional[Union[str, datetime]]) -> Optional[pd.Timestamp]:
    if x is None:
        return None
    if isinstance(x, datetime):
        return pd.Timestamp(x)
    return pd.Timestamp(x)

def _df_to_rows(df) -> List[Dict[str, Any]]:
    if df is None or getattr(df, "empty", True):
        return []
    # Stooq returns columns: Open, High, Low, Close, Volume
    df = df.dropna().sort_index()
    out: List[Dict[str, Any]] = []
    for ts, row in df.iterrows():
        t = pd.Timestamp(ts).to_pydatetime().replace(tzinfo=timezone.utc)
        out.append({
            "time": t,
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low":  float(row["Low"]),
            "close": float(row["Close"]),
            "volume": int(row.get("Volume", 0) or 0),
        })
    return out

def get_historical_prices_stooq(
    ticker: str,
    start_date: Optional[Union[str, datetime]] = None,
    end_date: Optional[Union[str, datetime]] = None,
) -> List[Dict[str, Any]]:
    t = ticker.strip().upper()
    sd = _to_date(start_date)
    ed = _to_date(end_date)

    # Try raw symbol, then try ".US" which Stooq often needs for US equities.
    for sym in (t, f"{t}.US"):
        try:
            df = pdr.get_data_stooq(sym, start=sd, end=ed)
            rows = _df_to_rows(df)
            if rows:
                return rows
        except Exception:
            continue
    return []
