#backend/app/routers/price.py
from fastapi import APIRouter, HTTPException, Query
from app.services.market_data import get_quote, get_candles_close

router = APIRouter(tags=["price"])

@router.get("/price")
def price(ticker: str = Query("AAPL")):
    p = get_quote(ticker)
    if p <= 0:
        raise HTTPException(status_code=404, detail="No price")
    return {"ticker": ticker.upper(), "price": p}

@router.get("/history")
def history(ticker: str = Query("AAPL"), days: int = Query(30, ge=1, le=365)):
    closes = get_candles_close(ticker, days=days)
    return {"ticker": ticker.upper(), "days": days, "closes": closes}
