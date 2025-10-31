#backend/app/routers/news.py
from fastapi import APIRouter, HTTPException, Query
from app.utils.validators import validate_ticker
from app.services.finnhub_client import fetch_company_news

router = APIRouter(prefix="/news", tags=["news"])

@router.get("")
def get_news(ticker: str = Query("AAPL", min_length=1, max_length=30)):
    try:
        t = validate_ticker(ticker)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ticker": t, "articles": fetch_company_news(t, count=25)}
