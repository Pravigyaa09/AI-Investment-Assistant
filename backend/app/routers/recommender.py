from __future__ import annotations

from math import sqrt
from statistics import pstdev
from typing import List, Optional, Dict

from fastapi import APIRouter, Query, Body, HTTPException

from app.services.market_data import (
    get_quote,
    get_candles_close,
    compute_volatility,
    simple_trend_score,
)
from app.services.finnhub_client import fetch_company_news

from pydantic import BaseModel, Field

from app.db.mongo import get_db
from app.services.recommender import evaluate_many

router = APIRouter(prefix="/ml", tags=["ml/recommender"])


def _sentiment_fallback(title: str) -> Dict[str, float | str]:
    """Keyword backstop if FinBERT isn’t available."""
    low = (title or "").lower()
    pos = ["surge", "jumps", "beats", "rises", "gain", "profit", "record", "soar", "up", "bull"]
    neg = ["falls", "misses", "slump", "drop", "loss", "cuts", "down", "plunge", "bear"]
    if any(w in low for w in pos):
        return {"label": "positive", "score": 0.66}
    if any(w in low for w in neg):
        return {"label": "negative", "score": 0.66}
    return {"label": "neutral", "score": 0.5}


def _news_with_sentiment(ticker: str, count: int) -> tuple[List[dict], Dict[str, int]]:
    """Fetch headlines and tag with FinBERT (or fallback). Return (items, counts)."""
    # Try FinBERT; if not loaded or unavailable we’ll fallback
    try:
        from app.nlp.finbert import FinBERT
        use_finbert = getattr(FinBERT, "is_available", lambda: False)()
    except Exception:
        FinBERT, use_finbert = None, False  # type: ignore

    news = fetch_company_news(ticker, count=count) or []
    counts = {"positive": 0, "neutral": 0, "negative": 0}
    out: List[dict] = []

    for n in news:
        title = n.get("title") or n.get("headline") or ""
        if not title:
            continue

        try:
            if use_finbert and FinBERT:
                pred = FinBERT.predict(title)
                label = pred.get("label", "neutral")
                score = float(pred.get("score", 0.0))
            else:
                fb = _sentiment_fallback(title)
                label = str(fb["label"])
                score = float(fb["score"]) if isinstance(fb.get("score"), (int, float)) else 0.0
        except Exception:
            label, score = "neutral", 0.0

        if label in counts:
            counts[label] += 1
        out.append({"title": title, "label": label, "score": score, "url": n.get("url")})

    return out, counts


def _estimate_return_and_risk(closes: List[float], horizon_days: int) -> dict:
    """
    Simple probabilistic estimate:
      - mean daily return μ from last N returns
      - daily sigma from returns’ stdev
      - Expected horizon return ≈ μ * horizon_days
      - VaR(95%) ~ 1.65 * sigma_daily * sqrt(horizon_days)
    Returns percentages (e.g., 2.3 => 2.3%).
    """
    N = len(closes)
    if N < 10:
        return {"ok": False, "reason": "insufficient_history"}

    # Clean & returns
    prices = [float(c) for c in closes if c and c > 0]
    if len(prices) < 10:
        return {"ok": False, "reason": "insufficient_history"}

    rets = []
    for i in range(1, len(prices)):
        p0, p1 = prices[i - 1], prices[i]
        if p0 <= 0:
            continue
        rets.append((p1 / p0) - 1.0)

    if len(rets) < 5:
        return {"ok": False, "reason": "insufficient_history"}

    mu = sum(rets) / len(rets)
    sigma_d = pstdev(rets) if len(rets) > 1 else 0.0
    exp_ret = mu * horizon_days
    var95 = 1.65 * sigma_d * sqrt(horizon_days)

    return {
        "ok": True,
        "mean_daily_return": mu * 100.0,
        "sigma_daily": sigma_d * 100.0,
        "expected_return_pct": exp_ret * 100.0,  # %
        "var95_pct": var95 * 100.0,              # %
    }


def _decision(expected_pct: float, var95_pct: float, trend_score: float) -> dict:
    """
    Combine expected return, downside risk (VaR), and trend to make a B/H/S suggestion.
    """
    # Confidence relative to downside (bounded)
    denom = max(1e-9, var95_pct)
    conf = min(0.99, abs(expected_pct) / denom)

    # Heuristic decision boundary
    if expected_pct >= 0.2 * var95_pct and trend_score > 0:
        action = "Buy"
    elif expected_pct <= -0.2 * var95_pct and trend_score < 0:
        action = "Sell"
    else:
        action = "Hold"

    return {"action": action, "confidence": round(conf, 3)}


def _risk_bucket(vol_annual: float) -> str:
    if vol_annual < 0.25:
        return "low"
    if vol_annual < 0.50:
        return "medium"
    return "high"


def _analyze_one(ticker: str, horizon_days: int, top_n_news: int) -> dict:
    t = (ticker or "").strip().upper()
    if not t:
        return {"ticker": ticker, "status": "error", "error": "blank ticker"}

    # Price + history
    price = float(get_quote(t))  # never raises (0.0 if failed)
    closes = get_candles_close(t, days=max(60, horizon_days + 10))
    if len(closes) < 5:
        return {"ticker": t, "status": "insufficient_data", "message": "not enough candles", "last_price": price}

    # Indicators
    trend = simple_trend_score(closes)
    vol_ann = compute_volatility(closes)
    risk_level = _risk_bucket(vol_ann)

    # Return & risk estimate
    rr = _estimate_return_and_risk(closes, horizon_days)
    if not rr.get("ok"):
        return {"ticker": t, "status": "insufficient_data", "message": rr.get("reason", "insufficient"), "last_price": price}

    expected_pct = float(rr["expected_return_pct"])
    var95_pct = float(rr["var95_pct"])

    # Decision
    decision = _decision(expected_pct, var95_pct, trend)

    # News + sentiment
    headlines, counts = _news_with_sentiment(t, count=top_n_news)

    return {
        "ticker": t,
        "status": "ok",
        "horizon_days": horizon_days,
        "last_price": round(price, 4),
        "features": {
            "trend_score": round(trend, 3),
            "volatility_annual": round(vol_ann, 4),
            "mean_daily_return_pct": round(float(rr["mean_daily_return"]), 4),
            "sigma_daily_pct": round(float(rr["sigma_daily"]), 4),
        },
        "forecast": {
            "expected_return_pct": round(expected_pct, 2),
            "var95_pct": round(var95_pct, 2),
            "risk_level": risk_level,
        },
        "decision": decision,
        "news": {
            "counts": counts,
            "headlines": headlines,
        },
        "note": "Heuristic model; not financial advice.",
    }


@router.get("/ml/recommend")
def recommend_get(
    ticker: Optional[str] = Query(None, description="Single ticker, e.g. NVDA"),
    tickers: Optional[str] = Query(None, description="Comma-separated list, e.g. NVDA,AAPL,MSFT"),
    horizon_days: int = Query(21, ge=5, le=120),
    top_n_news: int = Query(6, ge=1, le=20),
):
    if not ticker and not tickers:
        raise HTTPException(status_code=400, detail="Provide 'ticker' or 'tickers'")

    tick_list: List[str] = []
    if ticker:
        tick_list = [ticker]
    if tickers:
        tick_list = [t.strip() for t in tickers.split(",") if t.strip()]

    results = [_analyze_one(t, horizon_days, top_n_news) for t in tick_list]
    return results[0] if len(results) == 1 else {"results": results}


@router.post("/ml/recommend")
def recommend_post(
    payload: dict = Body(..., example={"tickers": ["NVDA", "AAPL"], "horizon_days": 21, "top_n_news": 6})
):
    tick_list = payload.get("tickers") or []
    if isinstance(tick_list, str):
        tick_list = [tick_list]
    if not tick_list:
        raise HTTPException(status_code=400, detail="Body must include 'tickers' as list or string")

    horizon_days = int(payload.get("horizon_days", 21))
    top_n_news = int(payload.get("top_n_news", 6))

    results = [_analyze_one(str(t), horizon_days, top_n_news) for t in tick_list]
    return results[0] if len(results) == 1 else {"results": results}
class EvalRequest(BaseModel):
    user_id: str = Field(..., description="User id (ObjectId hex or string id)")
    tickers: List[str] = Field(..., min_items=1)

@router.post("/recommend", summary="Evaluate actions for user & tickers")
async def recommend(req: EvalRequest):
    results = await evaluate_many(req.user_id, req.tickers)
    return {"count": len(results), "items": results}

@router.get("/recommendations", summary="Get latest saved recommendations")
async def list_recommendations(
    user_id: str = Query(..., description="User id"),
    tickers: Optional[str] = Query(None, description="Comma-separated tickers to filter"),
    limit: int = Query(100, ge=1, le=500),
):
    db = get_db()
    filt = {"user_id": user_id}  # adapt if you store ObjectId for users
    if tickers:
        tick_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
        filt["ticker"] = {"$in": tick_list}

    cur = db["recommendations"].find(filt).sort("updated_at", -1).limit(limit)
    items = []
    async for d in cur:
        d["id"] = str(d.pop("_id"))
        d["user_id"] = str(d.get("user_id"))
        items.append(d)
    return {"count": len(items), "items": items}
