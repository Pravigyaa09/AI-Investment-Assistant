#backend/app/routers/debug_providers.py
from fastapi import APIRouter, Query
from typing import Optional

from app.services.market_data import (
    debug_status,
    debug_clear_cache,
    get_candles_rows_for_chart,
)

router = APIRouter(tags=["_debug"])

@router.get("/_debug/providers")
def providers(
    ticker: str = Query("AAPL", min_length=1, max_length=15),
    days: int = Query(60, ge=2, le=1000),
    clear_cache: bool = Query(False, description="If true, clears in-memory caches first"),
):
    """
    Diagnostic endpoint:
    - Optionally clears caches
    - Fetches chart rows (dates + closes) and reports which provider was used
    - Returns env + availability info
    """
    if clear_cache:
        cleared = debug_clear_cache()
    else:
        cleared = {"cleared": "no"}

    dates, closes, provider = get_candles_rows_for_chart(ticker, days=days)
    status = debug_status()

    return {
        "ticker": ticker.upper().strip(),
        "days": days,
        "provider_used": provider,
        "points": len(closes),
        "sample": {
            "first_date": dates[0] if dates else None,
            "first_close": closes[0] if closes else None,
            "last_date": dates[-1] if dates else None,
            "last_close": closes[-1] if closes else None,
        },
        "status": status,
        **cleared,
    }
