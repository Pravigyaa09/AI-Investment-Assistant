# backend/app/services/recommender.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from bson import ObjectId

from app.db.mongo import get_db
from app.logger import get_logger
from app.services.market_data import (
    get_candles_close, compute_volatility, simple_trend_score, get_quote
)
from app.services.finnhub_client import fetch_company_news

log = get_logger(__name__)

def _sentiment_counts(titles: List[str]) -> Tuple[int, int, int]:
    """
    Return (pos, neg, neu) using FinBERT if available; else a simple keyword heuristic.
    """
    pos = neg = neu = 0
    try:
        from app.nlp.finbert import FinBERT
        use_finbert = getattr(FinBERT, "is_available", lambda: False)()
    except Exception:
        FinBERT = None  # type: ignore
        use_finbert = False

    for t in titles:
        if not t:
            neu += 1
            continue
        label = "neutral"
        if use_finbert and FinBERT:
            try:
                pred = FinBERT.predict(t)
                label = (pred or {}).get("label", "neutral")
            except Exception:
                label = "neutral"
        else:
            low = t.lower()
            if any(w in low for w in ["surge","jumps","beats","rises","gain","profit","record","bull"]):
                label = "positive"
            elif any(w in low for w in ["falls","misses","slump","drop","loss","cuts","bear","plunge"]):
                label = "negative"
            else:
                label = "neutral"

        if label == "positive": pos += 1
        elif label == "negative": neg += 1
        else: neu += 1

    return pos, neg, neu


def _sentiment_score(pos: int, neg: int, neu: int) -> float:
    tot = max(1, pos + neg + neu)
    return (pos - neg) / tot


def _decide_action(owned: bool, s_score: float, trend: float, vol_ann: float) -> Tuple[str, float, List[str]]:
    """
    Rules → (action, confidence, reasons[])
    - s_score in [-1, +1]  (FinBERT net)
    - trend in [-1, +1]    (vs SMA20)
    - vol_ann ~ 0..1+      (annualized)
    """
    reasons: List[str] = []

    # thresholds (tweak as needed)
    strong_pos = s_score >= 0.25
    strong_neg = s_score <= -0.30
    uptrend    = trend  >= 0.04
    downtrend  = trend  <= -0.06
    low_risk   = vol_ann <= 0.45
    high_risk  = vol_ann >= 0.70

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
            if downtrend:  reasons.append("downtrend")
            if high_risk:  reasons.append("high risk")
        else:
            action, conf = "HOLD", 0.65
            reasons += ["no strong sell signal"]

    # smooth confidence using magnitudes
    conf = min(0.95, max(conf, 0.5 + 0.25*abs(s_score) + 0.2*abs(trend)))
    return action, round(conf, 3), reasons


async def evaluate_one(user_id: str, ticker: str) -> Dict[str, Any]:
    """
    Compute features & action for (user, ticker) and upsert into Mongo.
    Returns the full recommendation document (with user_id as str).
    """
    t = ticker.strip().upper()
    db = get_db()
    uid = ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id  # support string ids too

    # are we holding it? Check portfolio.holdings embedded in users collection
    user = await db["users"].find_one({"_id": uid})
    owned = False
    if user and user.get("portfolio"):
        holdings = user["portfolio"].get("holdings", [])
        for h in holdings:
            if h.get("ticker") == t and float(h.get("quantity", 0)) > 0:
                owned = True
                break

    # features
    price = float(get_quote(t) or 0.0)
    closes = get_candles_close(t, days=60)
    trend = float(simple_trend_score(closes))
    vol_ann = float(compute_volatility(closes))

    news = fetch_company_news(t, count=8)
    titles = [(n.get("title") or n.get("headline") or "").strip() for n in news]
    pos, neg, neu = _sentiment_counts(titles)
    s_score = _sentiment_score(pos, neg, neu)

    action, confidence, reasons = _decide_action(owned, s_score, trend, vol_ann)

    doc = {
        "user_id": uid,
        "ticker": t,
        "owned": owned,
        "last_price": price,
        "features": {
            "trend": round(trend, 4),
            "volatility_ann": round(vol_ann, 4),
            "sentiment": {"pos": pos, "neg": neg, "neu": neu, "score": round(s_score, 4)},
        },
        "action": action,                # BUY | HOLD | SELL | AVOID
        "confidence": confidence,        # 0..1
        "reasons": reasons,
        "updated_at": datetime.now(tz=timezone.utc),
    }

    # upsert per (user, ticker)
    await db["recommendations"].update_one(
        {"user_id": uid, "ticker": t},
        {"$set": doc},
        upsert=True,
    )

    # convert for JSON response
    out = doc.copy()
    out["user_id"] = str(uid)
    return out


async def evaluate_many(user_id: str, tickers: List[str]) -> List[Dict[str, Any]]:
    tickers = [t.strip().upper() for t in tickers if t and t.strip()]
    results: List[Dict[str, Any]] = []
    for t in tickers:
        try:
            results.append(await evaluate_one(user_id, t))
        except Exception as e:
            log.exception("recommender failed for %s/%s: %s", user_id, t, e)
            results.append({"ticker": t, "error": str(e)})
    return results
