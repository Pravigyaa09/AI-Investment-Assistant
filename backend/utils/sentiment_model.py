# backend/utils/sentiment_model.py
import os
import logging
from typing import List, Sequence, Dict, Tuple

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

logger = logging.getLogger(__name__)

_MODEL_NAME = os.getenv("FINBERT_MODEL", "yiyanghkust/finbert-tone")

_tokenizer = None
_model = None
_id2label: Dict[int, str] = {}
_device = None


def _ensure_model():
    """Lazy-load the model once, avoid import-time download."""
    global _tokenizer, _model, _id2label, _device
    if _model is not None:
        return

    logger.info("Loading FinBERT model: %s", _MODEL_NAME)
    _tokenizer = AutoTokenizer.from_pretrained(_MODEL_NAME)
    _model = AutoModelForSequenceClassification.from_pretrained(_MODEL_NAME)
    _model.eval()

    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    _model.to(_device)

    cfg = _model.config
    if getattr(cfg, "id2label", None):
        _id2label = {int(k): v.lower() for k, v in cfg.id2label.items()}
    else:
        # Safe default if the config is missing mappings.
        _id2label = {0: "positive", 1: "negative", 2: "neutral"}

    logger.info("FinBERT ready on %s with labels %s", _device, _id2label)


@torch.inference_mode()
def _predict_logits(batch: List[str]) -> torch.Tensor:
    _ensure_model()
    texts = [(t or "").strip() for t in batch]
    enc = _tokenizer(
        texts,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=128,  # titles are short; bump if you pass full articles
    )
    enc = {k: v.to(_device) for k, v in enc.items()}
    out = _model(**enc)
    return out.logits


def analyze_sentiment(text: str) -> str:
    """Return 'positive' | 'negative' | 'neutral' for a single text."""
    logits = _predict_logits([text])
    probs = torch.softmax(logits, dim=-1)
    pred = int(torch.argmax(probs, dim=-1)[0].item())
    return _id2label.get(pred, "neutral")


def analyze_sentiments(texts: Sequence[str], batch_size: int = 16) -> List[str]:
    """Vectorized classification for speed."""
    labels: List[str] = []
    for i in range(0, len(texts), batch_size):
        logits = _predict_logits(list(texts[i:i + batch_size]))
        preds = torch.argmax(torch.softmax(logits, dim=-1), dim=-1).tolist()
        labels.extend([_id2label.get(int(p), "neutral") for p in preds])
    return labels


def analyze_sentiment_with_scores(text: str) -> Dict[str, float]:
    """Return class probabilities plus the top label."""
    logits = _predict_logits([text])
    probs = torch.softmax(logits, dim=-1)[0].tolist()
    scores = {_id2label[i]: float(p) for i, p in enumerate(probs)}
    scores["label"] = max(scores, key=scores.get)
    return scores


def tally(labels: Sequence[str]) -> Tuple[int, int, int]:
    """Count (positive, negative, neutral)."""
    pos = sum(l == "positive" for l in labels)
    neg = sum(l == "negative" for l in labels)
    neu = sum(l == "neutral" for l in labels)
    return pos, neg, neu


def map_sentiment_to_signal(positive: int, negative: int, neutral: int):
    total = positive + negative + neutral
    if total == 0:
        return {"signal": "Hold", "confidence": 0.0}

    pr = positive / total
    nr = negative / total
    neu = neutral / total

    # Make thresholds symmetric; tweak to taste.
    if pr >= 0.65:
        return {"signal": "Buy", "confidence": round(pr, 3)}
    if nr >= 0.65:
        return {"signal": "Sell", "confidence": round(nr, 3)}

    conf = max(neu, 1 - abs(pr - nr))
    return {"signal": "Hold", "confidence": round(conf, 3)}
