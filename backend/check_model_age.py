#!/usr/bin/env python3
"""
Check ML model training age and status

Usage:
    python check_model_age.py
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.ml.model_store import MODEL_PATH, load_model


def main():
    print("=" * 70)
    print("🔍 ML MODEL STATUS CHECK")
    print("=" * 70)

    # Check if model exists
    if not MODEL_PATH.exists():
        print("\n❌ NO MODEL FOUND")
        print(f"   Path: {MODEL_PATH}")
        print("\n💡 To train a model:")
        print("   python train_model.py")
        print("=" * 70)
        return

    # Get model age
    mod_time = MODEL_PATH.stat().st_mtime
    model_age = datetime.now() - datetime.fromtimestamp(mod_time)
    days_old = model_age.days
    hours_old = model_age.seconds // 3600

    # Load model details
    bundle = load_model()
    if not bundle:
        print("\n⚠️  MODEL FILE EXISTS BUT FAILED TO LOAD")
        print(f"   Path: {MODEL_PATH}")
        print("\n💡 Try retraining:")
        print("   python train_model.py")
        print("=" * 70)
        return

    # Display status
    print(f"\n✅ MODEL FOUND")
    print(f"   Path: {MODEL_PATH}")
    print(f"\n📅 Model Age:")
    print(f"   Last trained: {datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Age: {days_old} days, {hours_old} hours")

    # Age assessment
    if days_old == 0:
        status = "🟢 FRESH (trained today)"
    elif days_old < 7:
        status = "🟢 GOOD (< 1 week old)"
    elif days_old < 14:
        status = "🟡 AGING (1-2 weeks old, consider retraining soon)"
    elif days_old < 30:
        status = "🟠 OLD (2-4 weeks old, retrain recommended)"
    else:
        status = "🔴 STALE (> 1 month old, retrain ASAP)"

    print(f"   Status: {status}")

    # Model details
    print(f"\n📊 Model Details:")
    print(f"   Features: {len(bundle.get('features', []))} features")
    print(f"   Horizon: {bundle.get('horizon_days', 'unknown')} days")
    print(f"   Classifier: {type(bundle.get('clf')).__name__}")
    print(f"   Regressor: {type(bundle.get('reg')).__name__}")

    # Recommendations
    print("\n💡 Recommendations:")
    if days_old >= 14:
        print("   ⚠️  Model is aging - consider retraining:")
        print("      python train_model.py")
    elif days_old >= 30:
        print("   🚨 Model is stale - retrain immediately:")
        print("      python train_model.py")
    else:
        print("   ✅ Model is fresh - no action needed")
        print(f"   📆 Next recommended training: in {max(0, 7 - days_old)} days")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
