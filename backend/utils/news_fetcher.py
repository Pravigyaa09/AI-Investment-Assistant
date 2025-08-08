# backend/utils/news_fetcher.py
import os
import logging
from datetime import datetime, timedelta, timezone

import requests
import yfinance as yf

logger = logging.getLogger(__name__)


def _parse_ts(ts):
    """Handle unix timestamps from Finnhub (datetime) or yfinance (providerPublishTime)."""
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except Exception:
        logger.warning("Could not parse timestamp: %r", ts)
        return None


def _fetch_finnhub(ticker: str, lookback_days: int, limit: int):
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        return []

    today = datetime.now(tz=timezone.utc)
    from_date = (today - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    url = (
        "https://finnhub.io/api/v1/company-news"
        f"?symbol={ticker}&from={from_date}&to={to_date}&token={api_key}"
    )

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json() or []
    except Exception:
        logger.exception("Finnhub news fetch failed")
        return []

    articles = []
    for it in data[:limit]:
        articles.append({
            # normalized keys
            "headline": it.get("headline") or it.get("title") or "",
            "title": it.get("headline") or it.get("title") or "",
            "summary": it.get("summary") or "",
            "url": it.get("url") or it.get("link") or "",
            "source": it.get("source") or it.get("publisher") or "",
            "published": _parse_ts(it.get("datetime") or it.get("providerPublishTime")),
        })
    return articles


def _fetch_yfinance(ticker: str, limit: int):
    try:
        news = (yf.Ticker(ticker).news) or []
    except Exception:
        logger.exception("yfinance news fetch failed")
        return []

    articles = []
    for it in news[:limit]:
        articles.append({
            "headline": it.get("title") or "",
            "title": it.get("title") or "",
            "summary": it.get("summary") or "",
            "url": it.get("link") or "",
            "source": it.get("publisher") or "",
            "published": _parse_ts(it.get("providerPublishTime")),
        })
    return articles


def fetch_news(ticker: str, lookback_days: int = 7, limit: int = 25):
    """
    Return a list[dict] of normalized articles:
    - headline/title, summary, url, source, published (datetime|None)
    Tries Finnhub first (if FINNHUB_API_KEY set), falls back to yfinance.
    """
    articles = _fetch_finnhub(ticker, lookback_days, limit)
    if not articles:
        articles = _fetch_yfinance(ticker, limit)

    logger.info("Fetched %d articles for %s", len(articles), ticker)
    return articles
