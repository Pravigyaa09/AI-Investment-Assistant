#backend/app/routers/news.py
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from app.utils.validators import validate_ticker
from app.services.finnhub_client import fetch_company_news
from app.services.stock_categories import get_all_categories, get_category_tickers
from app.api.deps import get_current_user_mongo
from app.db import get_repository, UserRepository
from app.logger import get_logger
from app.ml.infer import recommend as ml_recommend

log = get_logger(__name__)
router = APIRouter(prefix="/news", tags=["news"])


async def _get_ml_recommendations_batch(user_id: str, tickers: List[str], owned_tickers: set) -> Dict[str, Dict[str, Any]]:
    """
    Get hybrid ML + Sentiment recommendations for multiple tickers in parallel.

    Args:
        user_id: User ID
        tickers: List of tickers to analyze
        owned_tickers: Set of tickers the user owns

    Returns:
        Dict mapping ticker to recommendation with action, confidence, sentiment_analysis, etc.
    """
    import asyncio

    results = {}

    # Create tasks for all tickers in parallel using asyncio.gather
    tasks = []
    task_map = {}  # Map task to ticker for result correlation
    for ticker in tickers:
        has_position = ticker in owned_tickers
        # Use ml_recommend which now includes sentiment analysis and position-awareness
        # Run in thread pool to avoid blocking
        task = asyncio.to_thread(
            ml_recommend,
            ticker,
            horizon_days=21,
            user_id=user_id,
            has_position=has_position
        )
        tasks.append(task)
        task_map[id(task)] = ticker

    # Wait for ALL tasks in parallel (not sequentially!)
    completed = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results in order
    for task, rec in zip(tasks, completed):
        ticker = task_map[id(task)]
        try:
            if isinstance(rec, Exception):
                raise rec
            results[ticker] = rec
        except Exception as e:
            log.warning(f"ML recommendation failed for {ticker}: {e}")
            # Fallback to simple recommendation
            results[ticker] = {
                "action": "Hold",
                "confidence": 0.5,
                "sentiment_analysis": {
                    "sentiment_index": 0.0,
                    "sentiment_strength": 0.0,
                    "positive": 0,
                    "negative": 0,
                    "neutral": 0
                },
                "has_position": ticker in owned_tickers,
                "position_aware": True,
                "recommendation_type": "hybrid"
            }

    return results

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

        # Get recommendations using hybrid ML + Sentiment system
        limited_tickers = tickers[:15]  # Limit to 15 tickers per category
        recommendations = await _get_ml_recommendations_batch(
            str(current_user["_id"]),
            limited_tickers,
            owned_tickers
        )

        # Fetch news for category tickers
        all_articles = []
        for ticker in limited_tickers:
            try:
                ticker_articles = fetch_company_news(ticker, count=5)

                # Get recommendation from hybrid ML + Sentiment system
                rec_data = recommendations.get(ticker, {
                    "action": "Hold",
                    "confidence": 0.5,
                    "sentiment_analysis": {
                        "sentiment_index": 0.0,
                        "sentiment_strength": 0.0,
                        "positive": 0,
                        "negative": 0,
                        "neutral": 0
                    },
                    "has_position": ticker in owned_tickers,
                    "position_aware": True,
                    "recommendation_type": "hybrid"
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

            # Get recommendations using hybrid ML + Sentiment system
            recommendations = await _get_ml_recommendations_batch(
                str(current_user["_id"]),
                general_tickers,
                set()  # No owned tickers
            )

            articles = []
            for ticker in general_tickers:
                try:
                    ticker_articles = fetch_company_news(ticker, count=5)
                    rec_data = recommendations.get(ticker, {
                        "action": "Hold",
                        "confidence": 0.5,
                        "sentiment_analysis": {
                            "sentiment_index": 0.0,
                            "sentiment_strength": 0.0,
                            "positive": 0,
                            "negative": 0,
                            "neutral": 0
                        },
                        "has_position": False,
                        "position_aware": True,
                        "recommendation_type": "hybrid"
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

        # Get recommendations using hybrid ML + Sentiment system
        recommendations = await _get_ml_recommendations_batch(
            str(current_user["_id"]),
            holdings_tickers,
            owned_tickers
        )

        all_articles = []
        for ticker in holdings_tickers:
            try:
                ticker_articles = fetch_company_news(ticker, count=10)

                rec_data = recommendations.get(ticker, {
                    "action": "Hold",
                    "confidence": 0.5,
                    "sentiment_analysis": {
                        "sentiment_index": 0.0,
                        "sentiment_strength": 0.0,
                        "positive": 0,
                        "negative": 0,
                        "neutral": 0
                    },
                    "has_position": ticker in owned_tickers,
                    "position_aware": True,
                    "recommendation_type": "hybrid"
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
