# backend/app/ml/infer.py
from __future__ import annotations
from typing import Dict, List

from app.ml.features import build_features
# Try to load a trained bundle if present; otherwise we fall back to rules
try:
    from app.ml.model_store import load_model  # expects dict with {clf, reg, features}
except Exception:
    def load_model():
        return None  # graceful fallback

from app.services.market_data import compute_volatility


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


def recommend(ticker: str, *, horizon_days: int = 21) -> Dict:
    """
    Produce a recommendation dict for a single ticker.
    Uses trained ML model if available; otherwise falls back to simple rules.

    Returns dict:
      {
        "ticker": "...",
        "action": "Buy|Hold|Sell",
        "confidence": float,
        "expected_return_h": float,   # horizon-days expected return
        "risk": {...},                # vol & VaR block
        "features_used": {...},       # features vector for transparency
        "sentiments": [...],          # recent FinBERT (or keyword) labeled headlines
        "provider": "ml" | "rules"
      }
    """
    fp = build_features(ticker)
    X = fp.X
    closes = fp.info.get("closes", [])
    sentiments = fp.info.get("sentiments", [])
    trend = float(X.get("trend", 0.0))

    # Always compute risk from prices
    risk = _risk_metrics(closes, horizon_days)

    bundle = load_model()
    if bundle:
        # ---- ML path ----
        clf = bundle.get("clf")
        reg = bundle.get("reg")
        feats: List[str] = bundle.get("features", [])
        # Vectorize in the trained feature order
        xv = [[float(X.get(f, 0.0)) for f in feats]]

        # Class probability -> action, confidence
        proba = clf.predict_proba(xv)[0]  # type: ignore[attr-defined]
        classes = list(clf.classes_)      # type: ignore[attr-defined]
        best_i = max(range(len(proba)), key=lambda i: proba[i])
        action = str(classes[best_i])
        conf = float(proba[best_i])

        # Expected forward return (regressor is optional)
        y_ret = float(reg.predict(xv)[0]) if reg is not None else 0.0  # type: ignore[union-attr]

        return {
            "ticker": ticker.upper(),
            "action": action,
            "confidence": round(conf, 4),
            "expected_return_h": round(y_ret, 4),
            "risk": {k: round(v, 6) for k, v in risk.items()},
            "features_used": X,
            "sentiments": sentiments,
            "provider": "ml",
        }

    # ---- Rules fallback ----
    pos_mean = float(X.get("news_pos_mean", 0.0))
    neg_mean = float(X.get("news_neg_mean", 0.0))
    action = _action_from_rule(trend, neg_mean, pos_mean)
    # naive expected return: blend trend + recent momentum
    exp_ret = 0.5 * trend + 0.25 * float(X.get("ret_5", 0.0)) + 0.25 * float(X.get("ret_10", 0.0))
    conf = min(0.95, max(0.55, abs(trend) + 0.5))

    return {
        "ticker": ticker.upper(),
            "action": action,
            "confidence": round(conf, 4),
            "expected_return_h": round(exp_ret, 4),
            "risk": {k: round(v, 6) for k, v in risk.items()},
            "features_used": X,
            "sentiments": sentiments,
            "provider": "rules",
    }
