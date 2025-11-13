#backend/app/routers/recommender.py
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Query, Body, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

# ML-based inference system
from app.ml.infer import recommend as ml_recommend
from app.ml.train import train_and_save
from app.ml.model_store import load_model, MODEL_PATH

# MongoDB integration
from app.db.mongo import get_db
from app.db import get_repository, UserRepository
from app.services.recommender import evaluate_many

router = APIRouter(prefix="/ml", tags=["ml/recommender"])


# ============================================================================
# ML-BASED RECOMMENDATION ENDPOINTS
# ============================================================================

async def _check_user_position(user_id: Optional[str], ticker: str) -> bool:
    """Check if user owns a stock in their portfolio"""
    if not user_id:
        return False

    try:
        user_repo = get_repository(UserRepository)
        portfolio = await user_repo.get_portfolio(user_id)
        if portfolio:
            for holding in portfolio.holdings:
                if holding.ticker.upper() == ticker.upper():
                    return True
    except Exception:
        pass  # Silently fail if portfolio lookup fails

    return False


@router.get("/recommend")
async def recommend_get(
    ticker: Optional[str] = Query(None, description="Single ticker, e.g. AAPL"),
    tickers: Optional[str] = Query(None, description="Comma-separated list, e.g. AAPL,MSFT,TSLA"),
    horizon_days: int = Query(21, ge=5, le=120, description="Forecast horizon in days"),
    user_id: Optional[str] = Query(None, description="Optional user ID for position-aware recommendations"),
):
    """
    Get ML-based trade recommendations for one or more tickers with position-aware sentiment filtering.

    Uses trained ML model if available, otherwise falls back to rule-based heuristics.

    Returns:
      - action: Buy|Hold|Sell|Don't Buy (position-aware if user_id provided)
      - confidence: float (0.0 to 1.0)
      - expected_return_h: horizon-days forward return estimate
      - risk: volatility and VaR metrics
      - sentiment_analysis: sentiment index and clarity metrics
      - ml_recommendation & sentiment_recommendation: component predictions
      - recommendation_type: "hybrid" (ML + Sentiment)

    Position-aware logic (when user_id provided):
      If you own the stock:
        - ML "Buy" + weak sentiment → "Hold"
        - Sentiment "Buy" → "Hold"
        - Sentiment "Sell" → "Sell"
      If you don't own the stock:
        - ML "Buy" + clear negative sentiment → "Don't Buy"
        - Sentiment "Buy" → "Buy"
        - Sentiment "Sell"/"Don't Buy" → "Don't Buy"
    """
    if not ticker and not tickers:
        raise HTTPException(status_code=400, detail="Provide 'ticker' or 'tickers'")

    tick_list: List[str] = []
    if ticker:
        tick_list = [ticker.strip().upper()]
    if tickers:
        tick_list.extend([t.strip().upper() for t in tickers.split(",") if t.strip()])

    # Remove duplicates while preserving order
    seen = set()
    tick_list = [t for t in tick_list if not (t in seen or seen.add(t))]  # type: ignore

    if not tick_list:
        raise HTTPException(status_code=400, detail="No valid tickers provided")

    results = []
    for t in tick_list:
        try:
            # Check if user owns this stock (position-aware recommendations)
            has_position = await _check_user_position(user_id, t)

            recommendation = ml_recommend(
                t,
                horizon_days=horizon_days,
                user_id=user_id,
                has_position=has_position
            )
            results.append(recommendation)
        except Exception as e:
            results.append({
                "ticker": t,
                "error": str(e),
                "status": "failed"
            })

    return results[0] if len(results) == 1 else {"count": len(results), "results": results}


class RecommendRequest(BaseModel):
    """Request model for POST /ml/recommend"""
    tickers: List[str] = Field(..., min_items=1, max_items=20, description="List of ticker symbols")
    horizon_days: int = Field(21, ge=5, le=120, description="Forecast horizon in days")
    user_id: Optional[str] = Field(None, description="Optional user ID for position-aware recommendations")


@router.post("/recommend")
async def recommend_post(payload: RecommendRequest):
    """
    Get ML-based trade recommendations for multiple tickers (POST version).

    Uses trained ML model if available with position-aware sentiment filtering.
    Falls back to rule-based heuristics if no model exists.
    """
    results = []
    for ticker in payload.tickers:
        try:
            # Check if user owns this stock
            has_position = await _check_user_position(payload.user_id, ticker.strip().upper())

            recommendation = ml_recommend(
                ticker.strip().upper(),
                horizon_days=payload.horizon_days,
                user_id=payload.user_id,
                has_position=has_position
            )
            results.append(recommendation)
        except Exception as e:
            results.append({
                "ticker": ticker.upper(),
                "error": str(e),
                "status": "failed"
            })

    return {"count": len(results), "results": results}


# ============================================================================
# MODEL TRAINING & STATUS ENDPOINTS
# ============================================================================

@router.get("/status")
def model_status():
    """
    Check ML model training status.

    Returns whether a trained model exists and can be loaded.
    """
    bundle = load_model()
    if bundle is None:
        return {
            "trained": False,
            "model_path": str(MODEL_PATH),
            "message": "No trained model found. Use POST /ml/train to train a model.",
            "features": None,
            "horizon_days": None
        }

    return {
        "trained": True,
        "model_path": str(MODEL_PATH),
        "message": "Trained ML model available",
        "features": bundle.get("features", []),
        "horizon_days": bundle.get("horizon_days"),
        "models": {
            "classifier": type(bundle.get("clf")).__name__ if bundle.get("clf") else None,
            "regressor": type(bundle.get("reg")).__name__ if bundle.get("reg") else None,
        }
    }


class TrainRequest(BaseModel):
    """Request model for POST /ml/train"""
    tickers: List[str] = Field(
        default=["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "JPM", "BAC", "WMT"],
        description="List of tickers to use for training data"
    )
    lookback_days: int = Field(240, ge=100, le=500, description="Historical days to collect per ticker")
    horizon_days: int = Field(21, ge=5, le=90, description="Forward-looking horizon for labels")


def _train_model_task(tickers: List[str], lookback_days: int, horizon_days: int):
    """Background task to train the model"""
    try:
        path = train_and_save(
            tickers=tickers,
            lookback_days=lookback_days,
            horizon_days=horizon_days
        )
        print(f"✓ Model trained successfully and saved to: {path}")
    except Exception as e:
        print(f"✗ Model training failed: {e}")
        raise


@router.post("/train")
def train_model(payload: TrainRequest, background_tasks: BackgroundTasks):
    """
    Train a new ML model for trade recommendations.

    This endpoint:
    1. Collects historical price + news data for the specified tickers
    2. Extracts features (technical indicators + FinBERT sentiment)
    3. Creates labels from forward returns (Buy/Sell/Hold)
    4. Trains Logistic Regression (classifier) + Random Forest (regressor)
    5. Saves the trained model bundle to _artifacts/

    Training runs in the background. Use GET /ml/status to check completion.

    **Warning**: Training can take several minutes depending on the number of tickers
    and lookback days (requires fetching historical data + news).
    """
    # Validate tickers
    if not payload.tickers or len(payload.tickers) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 tickers required for training"
        )

    if len(payload.tickers) > 50:
        raise HTTPException(
            status_code=400,
            detail="Maximum 50 tickers allowed for training (to avoid API rate limits)"
        )

    # Clean ticker list
    tickers = [t.strip().upper() for t in payload.tickers if t.strip()]

    # Schedule training as background task
    background_tasks.add_task(
        _train_model_task,
        tickers=tickers,
        lookback_days=payload.lookback_days,
        horizon_days=payload.horizon_days
    )

    return {
        "status": "training_started",
        "message": f"Model training started for {len(tickers)} tickers",
        "config": {
            "tickers": tickers,
            "lookback_days": payload.lookback_days,
            "horizon_days": payload.horizon_days
        },
        "note": "Training is running in the background. Use GET /ml/status to check completion."
    }


# ============================================================================
# USER-SPECIFIC RECOMMENDATIONS (MongoDB Integration)
# ============================================================================

class EvalRequest(BaseModel):
    """Request model for user-specific evaluation"""
    user_id: str = Field(..., description="User ID (ObjectId hex or string)")
    tickers: List[str] = Field(..., min_items=1, description="List of tickers to evaluate")


@router.post("/evaluate", summary="Evaluate trade actions for user & tickers")
async def evaluate_user_portfolio(req: EvalRequest):
    """
    Evaluate trade recommendations for a specific user's tickers.

    This integrates with the user's portfolio and saves recommendations to MongoDB.
    """
    results = await evaluate_many(req.user_id, req.tickers)
    return {"count": len(results), "items": results}


@router.get("/recommendations", summary="Get saved recommendations for user")
async def list_recommendations(
    user_id: str = Query(..., description="User ID"),
    tickers: Optional[str] = Query(None, description="Comma-separated tickers to filter"),
    limit: int = Query(100, ge=1, le=500, description="Max number of recommendations to return"),
):
    """
    Retrieve previously saved recommendations for a user from MongoDB.

    Optionally filter by specific tickers.
    """
    from bson import ObjectId
    db = get_db()

    # Convert user_id to ObjectId if valid, otherwise keep as string
    uid = ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id
    filt = {"user_id": uid}

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
