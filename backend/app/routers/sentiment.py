# backend/app/routers/sentiment.py
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from app.nlp.finbert import FinBERT
from app.core.config import settings
from app.logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/sentiment", tags=["sentiment"])

# Enhanced keyword fallback with more sophisticated scoring
def simple_sentiment(text: str) -> dict:
    """Enhanced keyword-based sentiment with confidence scoring"""
    t = (text or "").lower()
    
    # Expanded keyword sets with weights
    strong_pos = ["surge", "soar", "skyrocket", "boom", "rally", "breakthrough"]
    med_pos = ["jumps", "beats", "rises", "gain", "bull", "profit", "record", "growth", "up"]
    weak_pos = ["steady", "stable", "maintains", "holds"]
    
    strong_neg = ["crash", "plunge", "collapse", "devastating", "disaster"]
    med_neg = ["falls", "misses", "slump", "drop", "bear", "loss", "down", "cut", "decline"]
    weak_neg = ["concerns", "uncertainty", "challenges", "issues"]
    
    # Calculate sentiment score
    strong_pos_count = sum(1 for k in strong_pos if k in t)
    med_pos_count = sum(1 for k in med_pos if k in t)
    weak_pos_count = sum(1 for k in weak_pos if k in t)
    
    strong_neg_count = sum(1 for k in strong_neg if k in t)
    med_neg_count = sum(1 for k in med_neg if k in t)
    weak_neg_count = sum(1 for k in weak_neg if k in t)
    
    # Weighted scoring
    pos_score = strong_pos_count * 1.0 + med_pos_count * 0.7 + weak_pos_count * 0.3
    neg_score = strong_neg_count * 1.0 + med_neg_count * 0.7 + weak_neg_count * 0.3
    
    if pos_score > neg_score and pos_score > 0:
        confidence = min(0.8, 0.5 + (pos_score - neg_score) * 0.1)
        return {
            "label": "positive", 
            "score": confidence,
            "all_scores": {"positive": confidence, "neutral": 1-confidence, "negative": 0},
            "confidence": "high" if confidence > 0.7 else "medium"
        }
    elif neg_score > pos_score and neg_score > 0:
        confidence = min(0.8, 0.5 + (neg_score - pos_score) * 0.1)
        return {
            "label": "negative", 
            "score": confidence,
            "all_scores": {"negative": confidence, "neutral": 1-confidence, "positive": 0},
            "confidence": "high" if confidence > 0.7 else "medium"
        }
    else:
        return {
            "label": "neutral", 
            "score": 0.6,
            "all_scores": {"neutral": 0.6, "positive": 0.2, "negative": 0.2},
            "confidence": "low"
        }

# Pydantic Models
class SentimentIn(BaseModel):
    texts: List[str] = Field(..., description="List of texts to analyze")
    preprocess: bool = Field(True, description="Whether to preprocess the text")
    use_cache: bool = Field(True, description="Whether to use caching")

class EntitySentimentIn(BaseModel):
    text: str = Field(..., description="Text to analyze for entity-specific sentiment")

class SentimentDistributionIn(BaseModel):
    texts: List[str] = Field(..., description="Texts for distribution analysis")

class SentimentOut(BaseModel):
    label: str = Field(..., description="Sentiment label (positive/neutral/negative)")
    score: float = Field(..., description="Confidence score for the predicted label")
    all_scores: Optional[Dict[str, float]] = Field(None, description="Scores for all labels")
    confidence: Optional[str] = Field(None, description="Confidence level (high/medium/low)")

class EntitySentimentOut(BaseModel):
    overall_sentiment: SentimentOut
    entities: Dict[str, List[str]]
    entity_sentiment: Dict[str, SentimentOut]
    processed_text: str

class SentimentDistributionOut(BaseModel):
    distribution: Dict[str, float]
    average_score: float
    total_count: int
    confidence_stats: Dict[str, int]

# API Endpoints
@router.post("/analyze", response_model=List[SentimentOut])
async def analyze_sentiment(payload: SentimentIn):
    """
    Analyze sentiment for a list of texts.
    Enhanced version with caching, preprocessing, and detailed confidence scores.
    """
    try:
        if FinBERT.is_available():
            results = FinBERT.predict_batch(
                payload.texts, 
                use_cache=payload.use_cache,
                preprocess=payload.preprocess
            )
            return results
        else:
            # Enhanced fallback
            return [simple_sentiment(text) for text in payload.texts]
    
    except Exception as e:
        log.error(f"Sentiment analysis failed: {e}")
        # Fallback to simple sentiment on any error
        return [simple_sentiment(text) for text in payload.texts]

@router.post("/analyze-entities", response_model=EntitySentimentOut)
async def analyze_with_entities(payload: EntitySentimentIn):
    """
    Analyze sentiment with entity extraction and entity-specific sentiment.
    """
    if not FinBERT.is_available():
        raise HTTPException(status_code=503, detail="FinBERT model not available")
    
    try:
        result = FinBERT.analyze_with_entities(payload.text)
        return result
    except Exception as e:
        log.error(f"Entity sentiment analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Analysis failed")

@router.post("/distribution", response_model=SentimentDistributionOut)
async def analyze_sentiment_distribution(payload: SentimentDistributionIn):
    """
    Analyze sentiment distribution across multiple texts.
    Useful for understanding overall market sentiment, news sentiment trends, etc.
    """
    if not payload.texts:
        raise HTTPException(status_code=400, detail="No texts provided")
    
    try:
        if FinBERT.is_available():
            result = FinBERT.get_sentiment_distribution(payload.texts)
            return result
        else:
            # Fallback distribution analysis
            results = [simple_sentiment(text) for text in payload.texts]
            distribution = {"positive": 0, "neutral": 0, "negative": 0}
            total_score = 0
            
            for result in results:
                distribution[result["label"]] += 1
                if result["label"] == "positive":
                    total_score += result["score"]
                elif result["label"] == "negative":
                    total_score -= result["score"]
            
            return {
                "distribution": {k: v/len(results) for k, v in distribution.items()},
                "average_score": total_score / len(results),
                "total_count": len(results),
                "confidence_stats": {"high_confidence": 0, "medium_confidence": len(results), "low_confidence": 0}
            }
    
    except Exception as e:
        log.error(f"Distribution analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Distribution analysis failed")

@router.get("/health")
async def sentiment_health():
    """Check sentiment analysis service health"""
    is_available = FinBERT.is_available()
    cache_stats = FinBERT.get_cache_stats() if is_available else {}
    
    return {
        "finbert_available": is_available,
        "model_name": settings.FINBERT_MODEL,
        "cache_stats": cache_stats,
        "fallback_active": not is_available
    }

@router.post("/cache/clear")
async def clear_cache():
    """Clear the sentiment analysis cache"""
    if FinBERT.is_available():
        FinBERT.clear_cache()
        return {"message": "Cache cleared successfully"}
    else:
        return {"message": "FinBERT not available, no cache to clear"}

# Legacy endpoint for backward compatibility
@router.post("", response_model=List[SentimentOut])
async def analyze_sentiment_legacy(payload: SentimentIn):
    """Legacy endpoint - redirects to /analyze"""
    return await analyze_sentiment(payload)