# backend/app/routers/chart.py
from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any

from app.services.market_data import get_candles_rows_for_chart

router = APIRouter(tags=["chart"])

@router.get("/chart/series")
def chart_series(
    ticker: str = Query(..., min_length=1, max_length=15, description="Stock ticker, e.g., AAPL"),
    days: int = Query(180, ge=1, le=1000, description="Number of calendar days back"),
):
    """
    Return dates + closes for the last `days`.
    Response:
    {
      "ticker": "AAPL",
      "days": 180,
      "provider": "finnhub|yahoo|synthetic",
      "points": [
         {"date": "2025-05-01", "close": 189.23},
         ...
      ]
    }
    """
    try:
        dates, closes, provider = get_candles_rows_for_chart(ticker, days=days)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"failed to build chart series: {e}")

    if not closes or not dates or len(dates) != len(closes):
        raise HTTPException(status_code=404, detail="no chart data")

    points = [{"date": d, "close": float(c)} for d, c in zip(dates, closes)]
    return {
        "ticker": ticker.upper().strip(),
        "days": days,
        "provider": provider,
        "points": points,
    }
