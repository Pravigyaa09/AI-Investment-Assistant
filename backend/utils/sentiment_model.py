# backend/utils/sentiment_model.py
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

# Load once globally (fast after first call)
_tokenizer = AutoTokenizer.from_pretrained("yiyanghkust/finbert-tone")
_model = AutoModelForSequenceClassification.from_pretrained("yiyanghkust/finbert-tone")
_labels = ["positive", "negative", "neutral"]

def analyze_sentiment(text: str) -> str:
    inputs = _tokenizer(text, return_tensors="pt", truncation=True)
    with torch.no_grad():
        outputs = _model(**inputs)
        probs = torch.nn.functional.softmax(outputs.logits, dim=1)
    pred = torch.argmax(probs, dim=1).item()
    return _labels[pred]

def map_sentiment_to_signal(positive, negative, neutral):
    total = positive + negative + neutral
    if total == 0:
        return {"signal": "Hold", "confidence": 0.0}

    pr = positive / total
    nr = negative / total
    nrml = neutral / total

    if pr > 0.65:
        return {"signal": "Buy", "confidence": round(pr, 3)}
    elif nr > 0.5:
        return {"signal": "Sell", "confidence": round(nr, 3)}
    else:
        conf = max(nrml, 1 - abs(pr - nr))
        return {"signal": "Hold", "confidence": round(conf, 3)}
