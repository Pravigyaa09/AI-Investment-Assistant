# backend/app/nlp/finbert.py
from __future__ import annotations
import re
import time
from typing import Dict, List, Optional, Tuple
from functools import lru_cache
from app.core.config import settings
from app.logger import get_logger

log = get_logger(__name__)

# Try libs; don't crash if missing
try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
    from scipy.special import softmax
    import torch
    import numpy as np
    _LIBS_OK = True
except Exception as e:
    log.warning("FinBERT dependencies not available (%s). Using keyword fallback.", e)
    _LIBS_OK = False

# ProsusAI/finbert label order: positive, negative, neutral
_LABELS = ["positive", "negative", "neutral"]

class TextPreprocessor:
    """Enhanced text preprocessing for financial content"""
    
    @staticmethod
    def clean_financial_text(text: str) -> str:
        """Clean and normalize financial text"""
        if not text:
            return ""
        
        # Remove URLs, mentions, hashtags
        text = re.sub(r'http\S+|www\S+|@\w+|#\w+', '', text)
        
        # Normalize financial symbols
        text = re.sub(r'\$([A-Z]{1,5})', r'\1', text)  # $AAPL -> AAPL
        
        # Normalize numbers/percentages
        text = re.sub(r'(\d+\.?\d*)\s*%', r'\1 percent', text)
        text = re.sub(r'\$(\d+\.?\d*[KMB]?)', r'\1 dollars', text)
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        return text
    
    @staticmethod
    def extract_entities(text: str) -> Dict[str, List[str]]:
        """Extract financial entities (basic regex-based)"""
        entities = {
            'tickers': re.findall(r'\b[A-Z]{1,5}\b', text),
            'companies': re.findall(r'\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\b', text),
            'numbers': re.findall(r'\d+\.?\d*[KMB]?', text)
        }
        return entities

class SentimentCache:
    """Simple in-memory cache for sentiment results"""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.cache = {}
        self.timestamps = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
    
    def _is_expired(self, key: str) -> bool:
        return time.time() - self.timestamps.get(key, 0) > self.ttl_seconds
    
    def get(self, text: str) -> Optional[dict]:
        key = hash(text)
        if key in self.cache and not self._is_expired(str(key)):
            return self.cache[key]
        return None
    
    def set(self, text: str, result: dict):
        key = hash(text)
        
        # Clear expired entries if cache is full
        if len(self.cache) >= self.max_size:
            expired_keys = [k for k in self.cache.keys() if self._is_expired(str(k))]
            for k in expired_keys:
                self.cache.pop(k, None)
                self.timestamps.pop(str(k), None)
        
        self.cache[key] = result
        self.timestamps[str(key)] = time.time()

class FinBERT:
    _tok = None
    _model = None
    _pipeline = None
    _ready = False
    _cache = SentimentCache()
    _preprocessor = TextPreprocessor()

    @classmethod
    def is_available(cls) -> bool:
        """
        True if transformers/torch/scipy are installed and the model loads.
        Never raises; logs and returns False on failure.
        """
        if not _LIBS_OK:
            return False
        if cls._ready:
            return True
        try:
            name = settings.FINBERT_MODEL or "ProsusAI/finbert"
            cls._tok = AutoTokenizer.from_pretrained(name)
            cls._model = AutoModelForSequenceClassification.from_pretrained(name)
            cls._model.eval()
            
            # Also create a pipeline for easier batch processing
            cls._pipeline = pipeline(
                "sentiment-analysis",
                model=cls._model,
                tokenizer=cls._tok,
                top_k=None  # Return all scores (replaces deprecated return_all_scores=True)
            )
            
            cls._ready = True
            log.info("FinBERT loaded: %s", name)
            return True
        except Exception as e:
            log.warning("FinBERT load failed (%s). Falling back to keywords.", e)
            cls._tok = None
            cls._model = None
            cls._pipeline = None
            cls._ready = False
            return False

    @classmethod
    def predict(cls, text: str, use_cache: bool = True, preprocess: bool = True) -> dict:
        """
        Returns {"label": "positive|neutral|negative", "score": float, "all_scores": dict}.
        Raises RuntimeError if FinBERT isn't available.
        """
        if not cls.is_available():
            raise RuntimeError("FinBERT not available")
        
        # Check cache first
        if use_cache:
            cached = cls._cache.get(text)
            if cached:
                return cached
        
        # Preprocess text
        processed_text = cls._preprocessor.clean_financial_text(text) if preprocess else text
        
        # Get prediction
        tokens = cls._tok(processed_text, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            logits = cls._model(**tokens).logits[0].numpy()
        
        probs = softmax(logits)
        top_idx = int(probs.argmax())

        # Map probabilities to correct labels (ProsusAI/finbert order: positive, negative, neutral)
        result = {
            "label": _LABELS[top_idx],
            "score": float(probs[top_idx]),
            "all_scores": {
                "positive": float(probs[0]),  # Index 0 = positive
                "negative": float(probs[1]),  # Index 1 = negative
                "neutral": float(probs[2])    # Index 2 = neutral
            },
            "confidence": "high" if probs[top_idx] > 0.7 else "medium" if probs[top_idx] > 0.5 else "low"
        }
        
        # Cache result
        if use_cache:
            cls._cache.set(text, result)
        
        return result

    @classmethod
    def predict_batch(cls, texts: List[str], use_cache: bool = True, preprocess: bool = True) -> List[dict]:
        """
        Efficient batch prediction with caching.
        """
        if not cls.is_available():
            raise RuntimeError("FinBERT not available")
        
        results = []
        uncached_texts = []
        uncached_indices = []
        
        # Check cache for each text
        for i, text in enumerate(texts):
            if use_cache:
                cached = cls._cache.get(text)
                if cached:
                    results.append(cached)
                    continue
            
            uncached_texts.append(text)
            uncached_indices.append(i)
            results.append(None)  # placeholder
        
        # Process uncached texts in batch
        if uncached_texts:
            processed_texts = [
                cls._preprocessor.clean_financial_text(text) if preprocess else text 
                for text in uncached_texts
            ]
            
            # Use pipeline for efficient batch processing
            pipeline_results = cls._pipeline(processed_texts)
            
            # Convert pipeline results to our format
            for i, (original_text, pipeline_result) in enumerate(zip(uncached_texts, pipeline_results)):
                # Find the highest score result
                best_result = max(pipeline_result, key=lambda x: x['score'])
                
                # Create all_scores dict
                all_scores = {item['label'].lower(): item['score'] for item in pipeline_result}
                # Map pipeline labels to our labels if needed
                label_mapping = {
                    'LABEL_0': 'negative', 'LABEL_1': 'neutral', 'LABEL_2': 'positive',
                    'negative': 'negative', 'neutral': 'neutral', 'positive': 'positive'
                }
                
                final_label = label_mapping.get(best_result['label'].lower(), best_result['label'].lower())
                
                result = {
                    "label": final_label,
                    "score": best_result['score'],
                    "all_scores": all_scores,
                    "confidence": "high" if best_result['score'] > 0.7 else "medium" if best_result['score'] > 0.5 else "low"
                }
                
                # Cache and store result
                if use_cache:
                    cls._cache.set(original_text, result)
                
                # Put result in correct position
                original_idx = uncached_indices[i]
                results[original_idx] = result
        
        return results

    @classmethod
    def analyze_with_entities(cls, text: str) -> dict:
        """
        Enhanced analysis that includes entity extraction and entity-level sentiment.
        """
        if not cls.is_available():
            raise RuntimeError("FinBERT not available")
        
        # Get overall sentiment
        sentiment = cls.predict(text)
        
        # Extract entities
        entities = cls._preprocessor.extract_entities(text)
        
        # Analyze sentiment for each ticker mentioned
        entity_sentiment = {}
        for ticker in entities.get('tickers', []):
            # Create context around the ticker for more accurate sentiment
            ticker_contexts = []
            sentences = text.split('.')
            for sentence in sentences:
                if ticker in sentence:
                    ticker_contexts.append(sentence.strip())
            
            if ticker_contexts:
                # Analyze sentiment of ticker-specific context
                ticker_text = '. '.join(ticker_contexts)
                ticker_sentiment = cls.predict(ticker_text, use_cache=False)
                entity_sentiment[ticker] = ticker_sentiment
        
        return {
            "overall_sentiment": sentiment,
            "entities": entities,
            "entity_sentiment": entity_sentiment,
            "processed_text": cls._preprocessor.clean_financial_text(text)
        }

    @classmethod
    def get_sentiment_distribution(cls, texts: List[str]) -> dict:
        """
        Analyze sentiment distribution across multiple texts.
        """
        if not texts:
            return {"distribution": {}, "average_score": 0, "total_count": 0}
        
        results = cls.predict_batch(texts)
        
        # Calculate distribution
        distribution = {"positive": 0, "neutral": 0, "negative": 0}
        total_score = 0
        
        for result in results:
            distribution[result["label"]] += 1
            # Convert to -1 to 1 scale for averaging
            if result["label"] == "positive":
                total_score += result["score"]
            elif result["label"] == "negative":
                total_score -= result["score"]
            # neutral adds 0
        
        return {
            "distribution": {k: v/len(results) for k, v in distribution.items()},
            "average_score": total_score / len(results),
            "total_count": len(results),
            "confidence_stats": {
                "high_confidence": len([r for r in results if r.get("confidence") == "high"]),
                "medium_confidence": len([r for r in results if r.get("confidence") == "medium"]),
                "low_confidence": len([r for r in results if r.get("confidence") == "low"])
            }
        }

    @classmethod
    def clear_cache(cls):
        """Clear the sentiment cache"""
        cls._cache = SentimentCache()
        log.info("FinBERT cache cleared")

    @classmethod
    def get_cache_stats(cls) -> dict:
        """Get cache statistics"""
        return {
            "cache_size": len(cls._cache.cache),
            "max_size": cls._cache.max_size,
            "ttl_seconds": cls._cache.ttl_seconds
        }