# routes/marketdata.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from utils.data_loader import (
    fetch_price_history,
    fetch_intraday,
    fetch_latest_price,
    fetch_company_profile,
    add_returns,
    to_json_records,
)
from logger import get_logger

router = APIRouter(prefix="/market", tags=["market"])
logger = get_logger(__name__)


@router.get("/prices/{ticker}")
def get_prices(
    ticker: str,
    period: Optional[str] = Query("1y", description="e.g., 1mo, 3mo, 6mo, 1y, 5y, max"),
    interval: Optional[str] = Query("1d", description="e.g., 1m, 5m, 15m, 1h, 1d, 1wk, 1mo"),
    start: Optional[str] = Query(None, description="YYYY-MM-DD or ISO8601"),
    end: Optional[str] = Query(None, description="YYYY-MM-DD or ISO8601"),
    auto_adjust: bool = Query(True),
    prepost: bool = Query(False),
    with_returns: bool = Query(False, description="Append r_1, r_5, r_20 columns"),
    limit: Optional[int] = Query(None, description="Trim to last N rows"),
):
    """
    Daily/interval OHLCV. Provide (start/end) OR (period). If both provided, start/end wins.
    """
    df = fetch_price_history(
        ticker,
        start=start,
        end=end,
        period=period,
        interval=interval,
        auto_adjust=auto_adjust,
        prepost=prepost,
    )
    if df.empty:
        raise HTTPException(status_code=404, detail="No data available for requested params")

    if with_returns:
        df = add_returns(df)

    return {
        "symbol": ticker.upper(),
        "period": period,
        "interval": interval,
        "count": len(df if not limit else df.tail(limit)),
        "data": to_json_records(df, limit=limit),
    }


@router.get("/intraday/{ticker}")
def get_intraday(
    ticker: str,
    period: str = Query("5d", description="e.g., 1d, 5d, 1mo"),
    interval: str = Query("5m", description="e.g., 1m, 2m, 5m, 15m, 30m, 1h"),
    prepost: bool = Query(False),
    limit: Optional[int] = Query(None),
):
    """
    Intraday OHLCV (short periods only; yfinance caps period by interval).
    """
    df = fetch_intraday(ticker, period=period, interval=interval, prepost=prepost)
    if df.empty:
        raise HTTPException(status_code=404, detail="No intraday data available")
    return {
        "symbol": ticker.upper(),
        "period": period,
        "interval": interval,
        "count": len(df if not limit else df.tail(limit)),
        "data": to_json_records(df, limit=limit),
    }


@router.get("/latest/{ticker}")
def get_latest(ticker: str):
    """
    Best-effort latest price.
    """
    price = fetch_latest_price(ticker)
    if price is None:
        raise HTTPException(status_code=404, detail="Latest price unavailable")
    return {"symbol": ticker.upper(), "price": price}


@router.get("/profile/{ticker}")
def get_profile(ticker: str):
    """
    Small, stable subset of company fundamentals/metadata.
    """
    profile = fetch_company_profile(ticker)
    if "error" in profile:
        raise HTTPException(status_code=404, detail="Profile unavailable")
    return profile
