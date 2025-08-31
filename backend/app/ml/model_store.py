# backend/app/ml/model_store.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional
import joblib

MODEL_DIR = Path(__file__).resolve().parent / "_artifacts"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = MODEL_DIR / "recommender.pkl"

def save_model(bundle: Dict[str, Any]) -> str:
    joblib.dump(bundle, MODEL_PATH)
    return str(MODEL_PATH)

def load_model() -> Optional[Dict[str, Any]]:
    if not MODEL_PATH.exists():
        return None
    try:
        return joblib.load(MODEL_PATH)
    except Exception:
        return None
