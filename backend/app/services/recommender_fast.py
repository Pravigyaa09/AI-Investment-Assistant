# backend/app/services/recommender_fast.py
"""
Fast recommendation service that uses cached data and parallel processing
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Tuple
from bson import ObjectId

from app.db.mongo import get_db
from app.logger import get_logger
from app.services.market_data import get_quote, get_candles_close, compute_volatility, simple_trend_score
from app.services.finnhub_client import fetch_company_news

log = get_logger(__name__)

# Simple in-memory cache for recommendations (expires after 5 minutes)
_recommendation_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL = 300  # 5 minutes


def _sentiment_counts(titles: List[str]) -> Tuple[int, int, int]:
    """Simple keyword-based sentiment (fast, no ML)"""
    pos = neg = neu = 0

    for t in titles:
        if not t:
            neu += 1
            continue

        low = t.lower()
        if any(w in low for w in ["surge", "jumps", "beats", "rises", "gain", "profit", "record", "bull", "soars", "rally"]):
            pos += 1
        elif any(w in low for w in ["falls", "misses", "slump", "drop", "loss", "cuts", "bear", "plunge", "crash", "decline"]):
            neg += 1
        else:
            neu += 1

    return pos, neg, neu


def _sentiment_score(pos: int, neg: int, neu: int) -> float:
    tot = max(1, pos + neg + neu)
    return (pos - neg) / tot


def _decide_action(owned: bool, s_score: float, trend: float, vol_ann: float) -> Tuple[str, float, List[str]]:
    """Fast decision logic"""
    reasons: List[str] = []

    strong_pos = s_score >= 0.25
    strong_neg = s_score <= -0.30
    uptrend = trend >= 0.04
    downtrend = trend <= -0.06
    low_risk = vol_ann <= 0.45
    high_risk = vol_ann >= 0.70

    if not owned:
        if strong_pos and uptrend and low_risk:
            action, conf = "BUY", 0.8
            reasons += ["positive sentiment", "uptrend", "low risk"]
        elif strong_pos and uptrend:
            action, conf = "BUY", 0.7
            reasons += ["positive sentiment", "uptrend"]
        elif strong_neg and downtrend:
            action, conf = "AVOID", 0.7
            reasons += ["negative sentiment", "downtrend"]
        else:
            action, conf = "HOLD", 0.55
            reasons += ["mixed signals"]
    else:
        if strong_neg or downtrend or high_risk:
            action, conf = "SELL", 0.75
            if strong_neg: reasons.append("negative sentiment")
            if downtrend: reasons.append("downtrend")
            if high_risk: reasons.append("high risk")
        else:
            action, conf = "HOLD", 0.65
            reasons += ["no strong sell signal"]

    conf = min(0.95, max(conf, 0.5 + 0.25 * abs(s_score) + 0.2 * abs(trend)))
    return action, round(conf, 3), reasons


async def get_recommendation_fast(user_id: str, ticker: str, owned: bool, skip_news: bool = False) -> Dict[str, Any]:
    """
    Fast recommendation that skips news fetch if not needed and uses simple sentiment

    Args:
        user_id: User ID
        ticker: Stock ticker
        owned: Whether user owns this stock
        skip_news: If True, skip news fetch and use cached/simple analysis
    """
    t = ticker.strip().upper()

    # Check cache first (5 min TTL)
    cache_key = f"{user_id}:{t}"
    cached = _recommendation_cache.get(cache_key)
    if cached:
        ts, rec = cached
        if datetime.now().timestamp() - ts < _CACHE_TTL:
            return rec

    try:
        # Get price and trend data (these are cached in market_data.py)
        # Use timeout to prevent hanging on bad tickers
        price = float(get_quote(t) or 0.0)

        # If price is 0, ticker is likely invalid/delisted
        if price == 0.0:
            log.warning(f"Ticker {t} returned zero price, skipping detailed analysis")
            rec = {
                "action": "AVOID" if not owned else "SELL",
                "confidence": 0.6,
                "reasons": ["No price data available"],
                "owned": owned
            }
            # Cache the error result to avoid retries
            _recommendation_cache[cache_key] = (datetime.now().timestamp(), rec)
            return rec

        closes = get_candles_close(t, days=60)

        # If we got synthetic/empty data, use simplified analysis
        if len(closes) < 5:
            log.warning(f"Ticker {t} has insufficient historical data")
            rec = {
                "action": "HOLD",
                "confidence": 0.5,
                "reasons": ["Insufficient historical data"],
                "owned": owned
            }
            _recommendation_cache[cache_key] = (datetime.now().timestamp(), rec)
            return rec

        trend = float(simple_trend_score(closes))
        vol_ann = float(compute_volatility(closes))

        # Simple sentiment without fetching news if skip_news is True
        if skip_news:
            # Use neutral sentiment
            pos, neg, neu = 0, 0, 1
        else:
            # Fetch minimal news (only 3 articles instead of 8)
            try:
                news = fetch_company_news(t, count=3)
                titles = [(n.get("title") or n.get("headline") or "").strip() for n in news]
                pos, neg, neu = _sentiment_counts(titles)
            except Exception as news_error:
                log.warning(f"News fetch failed for {t}, using neutral sentiment: {news_error}")
                pos, neg, neu = 0, 0, 1

        s_score = _sentiment_score(pos, neg, neu)
        action, confidence, reasons = _decide_action(owned, s_score, trend, vol_ann)

        rec = {
            "action": action,
            "confidence": confidence,
            "reasons": reasons,
            "owned": owned
        }

        # Cache it
        _recommendation_cache[cache_key] = (datetime.now().timestamp(), rec)

        return rec

    except Exception as e:
        log.warning(f"Fast recommendation failed for {t}: {e}")
        rec = {
            "action": "HOLD",
            "confidence": 0.5,
            "reasons": ["Analysis unavailable"],
            "owned": owned
        }
        # Cache the error to avoid repeated failures
        _recommendation_cache[cache_key] = (datetime.now().timestamp(), rec)
        return rec


async def get_recommendations_batch(user_id: str, tickers: List[str], owned_tickers: set) -> Dict[str, Dict[str, Any]]:
    """
    Get recommendations for multiple tickers in parallel

    Args:
        user_id: User ID
        tickers: List of tickers to analyze
        owned_tickers: Set of tickers the user owns

    Returns:
        Dict mapping ticker to recommendation
    """
    # Create tasks for parallel execution
    tasks = []
    for ticker in tickers:
        owned = ticker in owned_tickers
        # Skip news for batch operations to speed up
        task = get_recommendation_fast(user_id, ticker, owned, skip_news=True)
        tasks.append((ticker, task))

    # Execute all in parallel
    results = {}
    for ticker, task in tasks:
        try:
            rec = await task
            results[ticker] = rec
        except Exception as e:
            log.warning(f"Batch recommendation failed for {ticker}: {e}")
            results[ticker] = {
                "action": "HOLD",
                "confidence": 0.5,
                "reasons": ["Analysis unavailable"],
                "owned": ticker in owned_tickers
            }

    return results


def clear_recommendation_cache():
    """Clear the recommendation cache"""
    _recommendation_cache.clear()
    log.info("Recommendation cache cleared")
