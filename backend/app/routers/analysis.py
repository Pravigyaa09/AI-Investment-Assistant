# backend/app/routers/analysis.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import pstdev
from typing import List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import get_repository, UserRepository
from app.api.deps import get_current_user_mongo
from app.services.market_data import (
    get_quote,
    get_candles_close,
    compute_volatility,
    simple_trend_score,
)
from app.services.finnhub_client import fetch_company_news

# Optional FinBERT (safe if not present)
try:
    from app.nlp.finbert import FinBERT
except Exception:
    FinBERT = None  # type: ignore

router = APIRouter(tags=["analysis"])

# ---------- helpers ----------
def _sentiment_fallback(title: str) -> dict:
    t = (title or "").lower()
    pos = ["surge", "jumps", "beats", "rises", "gain", "bull", "profit", "record", "soar"]
    neg = ["falls", "misses", "slump", "drop", "bear", "loss", "down", "plunge", "cut"]
    if any(w in t for w in pos): return {"label": "positive", "score": 0.66}
    if any(w in t for w in neg): return {"label": "negative", "score": 0.66}
    return {"label": "neutral", "score": 0.5}

def _sentiment(title: str) -> dict:
    try:
        if FinBERT and FinBERT.is_available():
            return FinBERT.predict(title or "")
    except Exception:
        pass
    return _sentiment_fallback(title)

def _daily_returns(closes: List[float]) -> List[float]:
    rets: List[float] = []
    for i in range(1, len(closes)):
        p0, p1 = closes[i-1], closes[i]
        if p0 and p0 > 0:
            rets.append(p1/p0 - 1.0)
    return rets

def _compute_rsi(closes: List[float], period: int = 14) -> float:
    """Calculate RSI indicator"""
    if len(closes) < period + 1:
        return 50.0

    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        if diff > 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))

    if len(gains) < period:
        return 50.0

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)

def _compute_sma(closes: List[float], period: int) -> float:
    """Calculate Simple Moving Average"""
    if len(closes) < period:
        return closes[-1] if closes else 0.0
    return sum(closes[-period:]) / period

def _compute_period_return(closes: List[float], days: int) -> float:
    """Calculate return over N days"""
    if len(closes) < days + 1:
        return 0.0
    start_price = closes[-(days + 1)]
    end_price = closes[-1]
    if start_price <= 0:
        return 0.0
    return (end_price / start_price) - 1.0

def _sentiment_index(items: List[dict]) -> float:
    vals: List[float] = []
    for s in items:
        lab = (s.get("label") or "neutral").lower()
        sc = float(s.get("score") or 0.0)
        if lab == "positive": vals.append(+sc)
        elif lab == "negative": vals.append(-sc)
    return sum(vals) / len(vals) if vals else 0.0

def _estimate_return_and_risk(closes: List[float], sentiments: List[dict], horizon_days: int = 21) -> Dict[str, float]:
    """
    Simple forward-return & risk estimate:
      mu = mean of ~60 daily returns
      sigma = stdev of daily returns
      mu_adj = mu + 0.002 * sentiment_index  ([-1..+1] -> ±0.2%/day bump)
      expected(h) = (1+mu_adj)^h - 1
      VaR95 (1d) ≈ max(0, 1.65*sigma - mu_adj)
    """
    window = min(60, max(2, len(closes)-1))
    rets = _daily_returns(closes[-(window+1):])
    mu = sum(rets)/len(rets) if rets else 0.0
    sigma = pstdev(rets) if len(rets) > 1 else 0.0

    s_idx = _sentiment_index(sentiments)  # [-1..+1]
    mu_adj = mu + 0.002 * s_idx

    exp_ret = (1.0 + mu_adj) ** horizon_days - 1.0
    vol_ann = sigma * (252 ** 0.5)
    var_95 = max(0.0, 1.65 * sigma - mu_adj)

    return {
        "expected_return_pct": round(exp_ret * 100.0, 3),
        "risk_vol_ann_pct": round(vol_ann * 100.0, 3),
        "var_95_daily_pct": round(var_95 * 100.0, 3),
        "sentiment_index": round(s_idx, 4),
    }

def _rule_signal(sentiment_index: float, has_position: bool = False, sentiment_strength: float = 0.5) -> tuple[str, float]:
    """
    Generate trade signal based on sentiment index and clarity.

    Sentiment Index ranges from -1.0 (very negative) to +1.0 (very positive).
    Sentiment Strength is the ratio of articles with clear sentiment vs neutral.

    This approach prevents weak "Buy/Sell" signals when sentiment is unclear.
    For example: 2 positive + 5 neutral + 1 negative = weak signal even if slightly positive.

    Thresholds:
      - sentiment_index > +0.30 AND strength ≥ 0.4 → Strong positive
      - sentiment_index < -0.30 AND strength ≥ 0.4 → Strong negative
      - Otherwise → Neutral/mixed (recommend Hold)

    If user owns stock (has_position=True):
      - Strong positive → Hold (keep it)
      - Strong negative → Sell (get rid of it)
      - Weak/Neutral → Hold (monitor)

    If user doesn't own stock (has_position=False):
      - Strong positive → Buy (acquire it)
      - Strong negative → Don't Buy (avoid it)
      - Weak/Neutral → Hold (wait for clarity)

    Args:
        sentiment_index: Weighted sentiment score from -1.0 to +1.0
        has_position: Whether user owns the stock
        sentiment_strength: Ratio of sentiment articles vs total (0.0-1.0)

    Returns:
        tuple of (action, confidence) where confidence = abs(sentiment_index) * strength
    """
    # Thresholds for strong signals
    POSITIVE_THRESHOLD = 0.30
    NEGATIVE_THRESHOLD = -0.30
    MIN_CLARITY = 0.40  # Need at least 40% of articles to have clear sentiment

    # Confidence = sentiment strength * clarity
    # This gives higher confidence when both sentiment is strong AND articles are clear
    confidence = abs(sentiment_index) * min(1.0, sentiment_strength)

    # Only consider signals "strong" if clarity is sufficient
    positive_signal = (sentiment_index > POSITIVE_THRESHOLD and sentiment_strength >= MIN_CLARITY)
    negative_signal = (sentiment_index < NEGATIVE_THRESHOLD and sentiment_strength >= MIN_CLARITY)

    if has_position:
        # User owns the stock
        if positive_signal:
            return "Hold", round(confidence, 3)  # Keep it, stock is doing well
        elif negative_signal:
            return "Sell", round(confidence, 3)  # Get rid of it, stock is struggling
        else:
            return "Hold", round(confidence, 3)  # Neutral/unclear → Hold, confidence reflects mixed sentiment
    else:
        # User doesn't own the stock
        if positive_signal:
            return "Buy", round(confidence, 3)  # Buy it, stock is doing well
        elif negative_signal:
            return "Don't Buy", round(confidence, 3)  # Don't buy, stock is struggling
        else:
            return "Hold", round(confidence, 3)  # Neutral/unclear → Hold, confidence reflects mixed sentiment

async def _analyze_one(
    ticker: str,
    *,
    days: int,
    top_n_news: int,
    horizon_days: int,
    user_id: Optional[str] = None
) -> Dict:
    t = (ticker or "").upper().strip()
    if not t:
        raise HTTPException(status_code=400, detail="ticker is required")

    price = float(get_quote(t))
    
    # Check if user has holding (MongoDB)
    position = None
    if user_id:
        user_repo = get_repository(UserRepository)
        portfolio = await user_repo.get_portfolio(user_id)
        if portfolio:
            for holding in portfolio.holdings:
                if holding.ticker == t:
                    mv = price * holding.quantity
                    cost = holding.avg_cost * holding.quantity
                    pnl_abs = mv - cost
                    pnl_pct = (pnl_abs / cost) if cost > 0 else 0.0
                    position = {
                        "quantity": holding.quantity,
                        "avg_cost": holding.avg_cost,
                        "last_price": price,
                        "market_value": round(mv, 2),
                        "pnl_abs": round(pnl_abs, 2),
                        "pnl_pct": round(pnl_pct, 4),
                    }
                    break

    closes = get_candles_close(t, days=days)
    trend = simple_trend_score(closes)
    vol_ann = compute_volatility(closes)

    # Calculate technical indicators
    rsi14 = _compute_rsi(closes, period=14)
    sma20 = _compute_sma(closes, period=20)
    sma50 = _compute_sma(closes, period=50)

    # Calculate multi-period returns
    ret_1 = _compute_period_return(closes, 1)
    ret_5 = _compute_period_return(closes, 5)
    ret_10 = _compute_period_return(closes, 10)
    ret_20 = _compute_period_return(closes, 20)

    # News + FinBERT
    news = fetch_company_news(t, count=top_n_news)
    counts = {"positive": 0, "neutral": 0, "negative": 0}
    sentiments: List[dict] = []
    for n in news:
        pred = _sentiment(n.get("title") or "")
        lab = (pred.get("label") or "neutral").lower()
        if lab in counts:
            counts[lab] += 1
        sentiments.append({
            "title": n.get("title"),
            "label": lab,
            "score": float(pred.get("score") or 0.0),
            "url": n.get("url"),
        })

    est = _estimate_return_and_risk(closes, sentiments, horizon_days=horizon_days)

    # Calculate sentiment_strength (clarity) = ratio of non-neutral articles
    sentiment_strength = 0.5  # Default if no articles
    if len(sentiments) > 0:
        non_neutral = counts.get("positive", 0) + counts.get("negative", 0)
        sentiment_strength = non_neutral / len(sentiments)  # Ratio of clear sentiment vs neutral

    # Use sentiment_index (more sophisticated than just counting articles)
    # Also consider clarity (sentiment_strength) to avoid weak mixed signals
    action, conf = _rule_signal(
        est["sentiment_index"],
        has_position=position is not None,
        sentiment_strength=sentiment_strength
    )
    combo_hint = "uptrend" if trend > 0 else ("downtrend" if trend < 0 else "flat")

    return {
        "ticker": t,
        "as_of": datetime.now(tz=timezone.utc).isoformat(),
        "has_position": position is not None,
        "position": position,
        "current_price": price,
        "trend_score": round(trend, 4),
        "volatility": round(vol_ann, 4),
        "rsi14": rsi14,
        "sma20": round(sma20, 2),
        "sma50": round(sma50, 2),
        "daily_return": round(ret_1, 4),
        "ret_5": round(ret_5, 4),
        "ret_10": round(ret_10, 4),
        "ret_20": round(ret_20, 4),
        "news_count": len(news),
        "news_positive_count": counts["positive"],
        "news_negative_count": counts["negative"],
        "news_neutral_count": counts["neutral"],
        "sentiment_index": est["sentiment_index"],
        "expected_return": round(est["expected_return_pct"] / 100.0, 4),
        "var_95": round(est["var_95_daily_pct"] / 100.0, 4),
        "sentiment_counts": counts,
        "sentiments": sentiments,
        "suggestion": {"action": action, "confidence": conf, "trend_hint": combo_hint},
        "note": "Estimates use recent drift + FinBERT sentiment; not financial advice.",
    }

# ---------- single-ticker ----------
@router.get("/stocks/{ticker}/analysis")
async def analyze_stock(
    ticker: str,
    days: int = Query(90, ge=10, le=365),
    top_n_news: int = Query(8, ge=1, le=25),
    horizon_days: int = Query(21, ge=5, le=90),
    current_user: Optional[dict] = Depends(get_current_user_mongo)
):
    user_id = str(current_user["_id"]) if current_user else None
    return await _analyze_one(
        ticker, 
        days=days, 
        top_n_news=top_n_news, 
        horizon_days=horizon_days,
        user_id=user_id
    )

# ---------- multi-ticker (batch) ----------
@router.get("/stocks/analysis")
async def analyze_stocks_batch(
    tickers: str = Query(..., description="Comma-separated list, e.g. AAPL,MSFT,TSLA"),
    days: int = Query(90, ge=10, le=365),
    top_n_news: int = Query(4, ge=1, le=15),
    horizon_days: int = Query(21, ge=5, le=90),
    current_user: Optional[dict] = Depends(get_current_user_mongo)
):
    # parse, de-dup, cap size to protect server
    raw = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    uniq: List[str] = []
    for t in raw:
        if t not in uniq:
            uniq.append(t)
    if not uniq:
        raise HTTPException(status_code=400, detail="no valid tickers provided")
    if len(uniq) > 20:
        uniq = uniq[:20]

    user_id = str(current_user["_id"]) if current_user else None
    results: List[Dict] = []
    for t in uniq:
        try:
            result = await _analyze_one(
                t, 
                days=days, 
                top_n_news=top_n_news, 
                horizon_days=horizon_days,
                user_id=user_id
            )
            results.append(result)
        except HTTPException as he:
            results.append({"ticker": t, "error": he.detail})
        except Exception as e:
            results.append({"ticker": t, "error": str(e)})

    return {"count": len(results), "results": results}

# Keep your debug endpoint
@router.post("/_debug/send-digest")
async def _debug_send_digest():
    try:
        from app.tasks.daily_digest import send_morning_digest
        return await send_morning_digest()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))