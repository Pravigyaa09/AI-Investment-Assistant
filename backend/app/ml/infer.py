# backend/app/ml/infer.py
from __future__ import annotations
from typing import Dict, List, Optional, Tuple

from app.ml.features import build_features
# Try to load a trained bundle if present; otherwise we fall back to rules
try:
    from app.ml.model_store import load_model  # expects dict with {clf, reg, features}
except Exception:
    def load_model():
        return None  # graceful fallback

from app.services.market_data import compute_volatility
from app.services.finnhub_client import fetch_company_news

# Optional FinBERT (safe if not present)
try:
    from app.nlp.finbert import FinBERT
except Exception:
    FinBERT = None  # type: ignore


def _sentiment_fallback(title: str) -> dict:
    """Fallback sentiment analysis using keyword matching"""
    t = (title or "").lower()
    pos = ["surge", "jumps", "beats", "rises", "gain", "bull", "profit", "record", "soar", "upgrade"]
    neg = ["falls", "misses", "slump", "drop", "bear", "loss", "down", "plunge", "cut", "downgrade"]
    if any(w in t for w in pos): return {"label": "positive", "score": 0.66}
    if any(w in t for w in neg): return {"label": "negative", "score": 0.66}
    return {"label": "neutral", "score": 0.5}


def _sentiment_predict(title: str) -> dict:
    """Get sentiment prediction from FinBERT or fallback"""
    try:
        if FinBERT and FinBERT.is_available():
            return FinBERT.predict(title or "")
    except Exception:
        pass
    return _sentiment_fallback(title)


def _sentiment_index(items: List[dict]) -> float:
    """Calculate weighted sentiment index from -1.0 (very negative) to +1.0 (very positive)"""
    vals: List[float] = []
    for s in items:
        lab = (s.get("label") or "neutral").lower()
        sc = float(s.get("score") or 0.0)
        if lab == "positive": vals.append(+sc)
        elif lab == "negative": vals.append(-sc)
    return sum(vals) / len(vals) if vals else 0.0


def _get_sentiment_analysis(ticker: str, top_n: int = 8) -> Dict[str, float]:
    """
    Get sentiment analysis for a ticker.

    Returns:
      {
        "sentiment_index": float,      # -1.0 to +1.0
        "sentiment_strength": float,   # 0.0 to 1.0 (ratio of clear sentiment articles)
        "positive": int,               # count of positive articles
        "negative": int,               # count of negative articles
        "neutral": int,                # count of neutral articles
      }
    """
    news = fetch_company_news(ticker.upper(), count=top_n) or []

    counts = {"positive": 0, "neutral": 0, "negative": 0}
    sentiments: List[dict] = []

    for article in news:
        title = article.get("title", "")
        pred = _sentiment_predict(title)
        lab = (pred.get("label") or "neutral").lower()

        if lab in counts:
            counts[lab] += 1

        sentiments.append({
            "label": lab,
            "score": float(pred.get("score") or 0.0)
        })

    # Calculate sentiment metrics
    sentiment_index = _sentiment_index(sentiments)

    # sentiment_strength = ratio of articles with clear sentiment vs neutral
    sentiment_strength = 0.5  # default
    if len(sentiments) > 0:
        non_neutral = counts.get("positive", 0) + counts.get("negative", 0)
        sentiment_strength = non_neutral / len(sentiments)

    return {
        "sentiment_index": round(sentiment_index, 4),
        "sentiment_strength": round(sentiment_strength, 4),
        "positive": counts["positive"],
        "negative": counts["negative"],
        "neutral": counts["neutral"],
    }


def _apply_position_aware_signal(
    sentiment_index: float,
    sentiment_strength: float,
    has_position: bool = False
) -> Tuple[str, float]:
    """
    Apply position-aware logic to sentiment analysis.

    If user owns stock (has_position=True):
      - Strong positive → Hold (keep it)
      - Strong negative → Sell (get rid of it)
      - Weak/Neutral → Hold (monitor)

    If user doesn't own stock (has_position=False):
      - Strong positive → Buy (acquire it)
      - Strong negative → Don't Buy (avoid it)
      - Weak/Neutral → Hold (wait for clarity)

    Args:
        sentiment_index: Weighted sentiment from -1.0 to +1.0
        sentiment_strength: Clarity ratio (0.0 to 1.0)
        has_position: Whether user owns the stock

    Returns:
        tuple of (action, confidence)
    """
    # Thresholds
    POSITIVE_THRESHOLD = 0.30
    NEGATIVE_THRESHOLD = -0.30
    MIN_CLARITY = 0.40  # Need at least 40% clear sentiment

    # Confidence = sentiment magnitude × clarity
    confidence = abs(sentiment_index) * min(1.0, sentiment_strength)

    # Only trigger strong signals with sufficient clarity
    positive_signal = (sentiment_index > POSITIVE_THRESHOLD and sentiment_strength >= MIN_CLARITY)
    negative_signal = (sentiment_index < NEGATIVE_THRESHOLD and sentiment_strength >= MIN_CLARITY)

    if has_position:
        # User owns the stock
        if positive_signal:
            return "Hold", round(confidence, 3)  # Keep it
        elif negative_signal:
            return "Sell", round(confidence, 3)  # Get rid of it
        else:
            return "Hold", round(confidence, 3)  # Neutral → Hold
    else:
        # User doesn't own the stock
        if positive_signal:
            return "Buy", round(confidence, 3)  # Acquire it
        elif negative_signal:
            return "Don't Buy", round(confidence, 3)  # Avoid it
        else:
            return "Hold", round(confidence, 3)  # Neutral → Hold


def _risk_metrics(closes: List[float], horizon_days: int) -> Dict[str, float]:
    """Basic risk block: annual vol, daily vol, horizon sigma, 95% VaR approx."""
    vol_ann = compute_volatility(closes)
    vol_daily = vol_ann / (252 ** 0.5) if vol_ann else 0.0
    sigma_h = vol_daily * (horizon_days ** 0.5)
    var95 = 1.65 * sigma_h  # ~one-sided 95%
    return {
        "vol_annual": float(vol_ann),
        "vol_daily": float(vol_daily),
        "sigma_h": float(sigma_h),
        "var95_h": float(var95),
    }


def _action_from_rule(trend: float, neg_mean: float, pos_mean: float) -> str:
    """Very conservative, transparent fallback when no model is saved yet."""
    if trend > 0.03 and pos_mean > neg_mean + 0.05:
        return "Buy"
    if trend < -0.02 and neg_mean > pos_mean + 0.05:
        return "Sell"
    return "Hold"


def recommend(
    ticker: str,
    *,
    horizon_days: int = 21,
    user_id: Optional[str] = None,
    has_position: bool = False
) -> Dict:
    """
    Produce a recommendation dict for a single ticker.

    Uses trained ML model if available with position-aware sentiment filtering.
    Falls back to rules if no model exists.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")
        horizon_days: Forecast horizon in days (5-120)
        user_id: Optional user ID (for future portfolio lookup)
        has_position: Whether user owns the stock

    Returns dict:
      {
        "ticker": "...",
        "action": "Buy|Hold|Sell|Don't Buy",
        "confidence": float,
        "expected_return_h": float,       # horizon-days expected return
        "risk": {...},                    # vol & VaR block
        "features_used": {...},           # features vector
        "sentiments": [...],              # recent articles with sentiment labels
        "sentiment_analysis": {...},      # sentiment metrics
        "provider": "ml" | "rules",
        "recommendation_type": "hybrid",  # ML + Sentiment
        "has_position": bool,
        "position_aware": bool
      }
    """
    fp = build_features(ticker)
    X = fp.X
    closes = fp.info.get("closes", [])
    sentiments = fp.info.get("sentiments", [])
    trend = float(X.get("trend", 0.0))

    # Always compute risk from prices
    risk = _risk_metrics(closes, horizon_days)

    # Get sentiment analysis
    sentiment_data = _get_sentiment_analysis(ticker, top_n=8)
    sentiment_index = sentiment_data["sentiment_index"]
    sentiment_strength = sentiment_data["sentiment_strength"]

    bundle = load_model()

    if bundle:
        # ---- ML path with sentiment filtering ----
        clf = bundle.get("clf")
        reg = bundle.get("reg")
        feats: List[str] = bundle.get("features", [])

        # Vectorize in the trained feature order
        xv = [[float(X.get(f, 0.0)) for f in feats]]

        # Get ML prediction
        proba = clf.predict_proba(xv)[0]  # type: ignore[attr-defined]
        classes = list(clf.classes_)      # type: ignore[attr-defined]
        best_i = max(range(len(proba)), key=lambda i: proba[i])
        raw_ml_action = str(classes[best_i])
        ml_conf = float(proba[best_i])

        # Expected forward return (regressor is optional)
        y_ret = float(reg.predict(xv)[0]) if reg is not None else 0.0  # type: ignore[union-attr]

        # Apply position-aware logic to ML prediction
        # ML model doesn't know about positions, so adjust its output
        ml_action = raw_ml_action
        if has_position:
            # User owns the stock
            if raw_ml_action == "Buy":
                ml_action = "Hold"  # Already own it, keep it
        else:
            # User doesn't own the stock - be more conservative
            if raw_ml_action == "Sell":
                ml_action = "Don't Buy"  # Don't own it, avoid buying
            elif raw_ml_action == "Buy":
                # Convert Buy to Hold if conditions aren't ideal
                # This prevents "buy everything" syndrome and encourages waiting for better entry points

                # Rule 1: If sentiment is weakly positive or neutral → Hold
                if sentiment_index < 0.35 and sentiment_strength >= 0.3:
                    ml_action = "Hold"

                # Rule 2: If ML confidence is moderate (not strong) → Hold
                elif ml_conf < 0.75:
                    ml_action = "Hold"

                # Rule 3: If sentiment clarity is very weak → Hold (unclear signal)
                elif sentiment_strength < 0.40:
                    ml_action = "Hold"

        # Apply position-aware sentiment logic to ML prediction
        sentiment_action, sentiment_conf = _apply_position_aware_signal(
            sentiment_index,
            sentiment_strength,
            has_position=has_position
        )

        # Blend ML and sentiment signals
        # Use average confidence weighted by clarity
        blended_conf = (ml_conf + sentiment_conf) / 2.0

        # For final action:
        # - If sentiment is very weak (clarity < 30%), trust position-aware ML
        # - If sentiment is clear (clarity >= 40%), blend both signals
        # - Prefer sentiment if it contradicts ML strongly and is clear
        final_action = ml_action
        final_conf = ml_conf

        if sentiment_strength >= 0.4:  # Sufficient clarity
            # Consider sentiment signal
            if sentiment_action != "Hold":
                # Strong sentiment signal overrides weak ML signal
                if ml_conf < 0.65:  # ML is uncertain
                    final_action = sentiment_action
                    final_conf = sentiment_conf
                else:
                    # Both have opinions - use blended confidence
                    final_action = ml_action
                    final_conf = blended_conf

        return {
            "ticker": ticker.upper(),
            "action": final_action,
            "confidence": round(final_conf, 4),
            "expected_return_h": round(y_ret, 4),
            "risk": {k: round(v, 6) for k, v in risk.items()},
            "features_used": X,
            "sentiments": sentiments,
            "sentiment_analysis": sentiment_data,
            "ml_recommendation": {
                "action": raw_ml_action,
                "confidence": round(ml_conf, 4)
            },
            "sentiment_recommendation": {
                "action": sentiment_action,
                "confidence": round(sentiment_conf, 4)
            },
            "provider": "ml",
            "recommendation_type": "hybrid",
            "has_position": has_position,
            "position_aware": True,
        }

    # ---- Rules fallback with sentiment enhancement ----
    pos_mean = float(X.get("news_pos_mean", 0.0))
    neg_mean = float(X.get("news_neg_mean", 0.0))
    raw_rule_action = _action_from_rule(trend, neg_mean, pos_mean)

    # Apply position-aware logic to rule-based action
    rule_action = raw_rule_action
    if has_position:
        # User owns the stock
        if raw_rule_action == "Buy":
            rule_action = "Hold"  # Already own it, keep it
    else:
        # User doesn't own the stock - be more conservative
        if raw_rule_action == "Sell":
            rule_action = "Don't Buy"  # Don't own it, avoid buying
        elif raw_rule_action == "Buy":
            # Convert Buy to Hold if conditions aren't ideal
            # This prevents "buy everything" syndrome and encourages waiting for better entry points

            # Rule 1: If sentiment is weakly positive or neutral → Hold
            if sentiment_index < 0.35 and sentiment_strength >= 0.3:
                rule_action = "Hold"

            # Rule 2: If rule confidence is moderate (not strong) → Hold
            elif rule_conf < 0.70:
                rule_action = "Hold"

            # Rule 3: If sentiment clarity is very weak → Hold (unclear signal)
            elif sentiment_strength < 0.40:
                rule_action = "Hold"

    # Apply sentiment position-aware logic to rules-based action
    sentiment_action, sentiment_conf = _apply_position_aware_signal(
        sentiment_index,
        sentiment_strength,
        has_position=has_position
    )

    # Blend rule-based with sentiment
    exp_ret = 0.5 * trend + 0.25 * float(X.get("ret_5", 0.0)) + 0.25 * float(X.get("ret_10", 0.0))
    rule_conf = min(0.95, max(0.55, abs(trend) + 0.5))

    # Use sentiment if it has sufficient clarity
    final_action = rule_action
    final_conf = rule_conf

    if sentiment_strength >= 0.4 and sentiment_action != "Hold":
        final_action = sentiment_action
        final_conf = sentiment_conf

    return {
        "ticker": ticker.upper(),
        "action": final_action,
        "confidence": round(final_conf, 4),
        "expected_return_h": round(exp_ret, 4),
        "risk": {k: round(v, 6) for k, v in risk.items()},
        "features_used": X,
        "sentiments": sentiments,
        "sentiment_analysis": sentiment_data,
        "rule_recommendation": {
            "action": raw_rule_action,
            "confidence": round(rule_conf, 4)
        },
        "sentiment_recommendation": {
            "action": sentiment_action,
            "confidence": round(sentiment_conf, 4)
        },
        "provider": "rules",
        "recommendation_type": "hybrid",
        "has_position": has_position,
        "position_aware": True,
    }
