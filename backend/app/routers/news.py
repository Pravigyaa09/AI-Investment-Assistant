#backend/app/routers/news.py
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from app.utils.validators import validate_ticker
from app.services.finnhub_client import fetch_company_news
from app.services.stock_categories import get_all_categories, get_category_tickers
from app.services.recommender_fast import get_recommendations_batch
from app.api.deps import get_current_user_mongo
from app.db import get_repository, UserRepository
from app.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/news", tags=["news"])

@router.get("")
def get_news(ticker: str = Query("AAPL", min_length=1, max_length=30)):
    """Get news for a specific ticker"""
    try:
        t = validate_ticker(ticker)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ticker": t, "articles": fetch_company_news(t, count=25)}


@router.get("/personalized")
async def get_personalized_news(
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user_mongo)
):
    """Get personalized news based on user's portfolio holdings"""
    try:
        user_repo: UserRepository = get_repository(UserRepository)
        portfolio = await user_repo.get_portfolio(str(current_user["_id"]))

        if not portfolio or not portfolio.holdings:
            # No holdings, return general market news
            general_tickers = ["SPY", "QQQ", "AAPL"]
            articles = []
            for ticker in general_tickers:
                try:
                    ticker_articles = fetch_company_news(ticker, count=5)
                    articles.extend(ticker_articles)
                except Exception as e:
                    log.warning(f"Failed to fetch news for {ticker}: {e}")

            return {
                "holdings": [],
                "articles": articles[:limit],
                "total": len(articles[:limit])
            }

        # Fetch news for each holding
        holdings_tickers = [h.ticker for h in portfolio.holdings]
        all_articles = []

        for ticker in holdings_tickers:
            try:
                ticker_articles = fetch_company_news(ticker, count=10)
                all_articles.extend(ticker_articles)
            except Exception as e:
                log.warning(f"Failed to fetch news for {ticker}: {e}")
                continue

        # Sort by published date (most recent first)
        all_articles.sort(
            key=lambda x: x.get("published_at") or "",
            reverse=True
        )

        return {
            "holdings": holdings_tickers,
            "articles": all_articles[:limit],
            "total": len(all_articles[:limit])
        }

    except Exception as e:
        log.error(f"Error fetching personalized news: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch personalized news"
        )


@router.get("/categories")
def get_categories():
    """Get all available stock categories"""
    return {"categories": get_all_categories()}


@router.get("/category/{category_key}")
async def get_category_news(
    category_key: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user_mongo)
):
    """Get news for a specific category with AI recommendations (FAST VERSION)"""
    try:
        # Get tickers for this category
        tickers = get_category_tickers(category_key)

        if not tickers:
            raise HTTPException(status_code=404, detail=f"Category '{category_key}' not found")

        # Get user's portfolio to check ownership
        user_repo: UserRepository = get_repository(UserRepository)
        portfolio = await user_repo.get_portfolio(str(current_user["_id"]))
        owned_tickers = set()
        if portfolio and portfolio.holdings:
            owned_tickers = {h.ticker for h in portfolio.holdings}

        # Get recommendations for all tickers in parallel (FAST!)
        limited_tickers = tickers[:15]  # Limit to 15 tickers per category
        recommendations = await get_recommendations_batch(
            str(current_user["_id"]),
            limited_tickers,
            owned_tickers
        )

        # Fetch news for category tickers
        all_articles = []
        for ticker in limited_tickers:
            try:
                ticker_articles = fetch_company_news(ticker, count=5)

                # Get pre-computed recommendation from batch
                rec_data = recommendations.get(ticker, {
                    "action": "HOLD",
                    "confidence": 0.5,
                    "reasons": ["Analysis unavailable"],
                    "owned": ticker in owned_tickers
                })

                # Attach recommendation to each article
                for article in ticker_articles:
                    article["recommendation"] = rec_data

                all_articles.extend(ticker_articles)
            except Exception as e:
                log.warning(f"Failed to fetch news for {ticker}: {e}")
                continue

        # Sort by published date
        all_articles.sort(
            key=lambda x: x.get("published_at") or "",
            reverse=True
        )

        return {
            "category": category_key,
            "tickers": tickers,
            "articles": all_articles[:limit],
            "total": len(all_articles[:limit])
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error fetching category news: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch category news"
        )


@router.get("/personalized/with-recommendations")
async def get_personalized_news_with_recommendations(
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user_mongo)
):
    """Get personalized news with AI buy/sell/hold recommendations (FAST VERSION)"""
    try:
        user_repo: UserRepository = get_repository(UserRepository)
        portfolio = await user_repo.get_portfolio(str(current_user["_id"]))

        if not portfolio or not portfolio.holdings:
            # No holdings, return general market news
            general_tickers = ["SPY", "QQQ", "AAPL"]

            # Get recommendations in batch (FAST!)
            recommendations = await get_recommendations_batch(
                str(current_user["_id"]),
                general_tickers,
                set()  # No owned tickers
            )

            articles = []
            for ticker in general_tickers:
                try:
                    ticker_articles = fetch_company_news(ticker, count=5)
                    rec_data = recommendations.get(ticker, {
                        "action": "HOLD",
                        "confidence": 0.5,
                        "reasons": ["Analysis unavailable"],
                        "owned": False
                    })

                    for article in ticker_articles:
                        article["recommendation"] = rec_data

                    articles.extend(ticker_articles)
                except Exception as e:
                    log.warning(f"Failed to fetch news for {ticker}: {e}")

            return {
                "holdings": [],
                "articles": articles[:limit],
                "total": len(articles[:limit])
            }

        # Fetch news for each holding with recommendations
        holdings_tickers = [h.ticker for h in portfolio.holdings]
        owned_tickers = set(holdings_tickers)

        # Get recommendations for all holdings in batch (FAST!)
        recommendations = await get_recommendations_batch(
            str(current_user["_id"]),
            holdings_tickers,
            owned_tickers
        )

        all_articles = []
        for ticker in holdings_tickers:
            try:
                ticker_articles = fetch_company_news(ticker, count=10)

                rec_data = recommendations.get(ticker, {
                    "action": "HOLD",
                    "confidence": 0.5,
                    "reasons": ["Analysis unavailable"],
                    "owned": ticker in owned_tickers
                })

                for article in ticker_articles:
                    article["recommendation"] = rec_data

                all_articles.extend(ticker_articles)
            except Exception as e:
                log.warning(f"Failed to fetch news for {ticker}: {e}")
                continue

        # Sort by published date (most recent first)
        all_articles.sort(
            key=lambda x: x.get("published_at") or "",
            reverse=True
        )

        return {
            "holdings": holdings_tickers,
            "articles": all_articles[:limit],
            "total": len(all_articles[:limit])
        }

    except Exception as e:
        log.error(f"Error fetching personalized news with recommendations: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch personalized news with recommendations"
        )
