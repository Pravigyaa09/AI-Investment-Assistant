#!/usr/bin/env python3
"""
Standalone script to train the ML-based trade recommender model.

Usage:
    python train_model.py
    python train_model.py --tickers AAPL MSFT GOOGL TSLA
    python train_model.py --lookback-days 300 --horizon-days 21
"""

import sys
import argparse
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.ml.train import train_and_save
from app.ml.model_store import MODEL_PATH


def main():
    parser = argparse.ArgumentParser(
        description="Train ML model for trade recommendations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Train with default tickers (10 major stocks)
  python train_model.py

  # Train with custom tickers
  python train_model.py --tickers AAPL MSFT GOOGL AMZN TSLA NVDA META

  # Train with more historical data
  python train_model.py --lookback-days 365 --horizon-days 30

  # Train with many tickers (diversified dataset)
  python train_model.py --tickers AAPL MSFT GOOGL AMZN TSLA NVDA META \\
                                   JPM BAC WMT TGT COST HD LOW \\
                                   DIS NFLX CRM ADBE

Note: Training may take several minutes depending on the number of tickers
      and lookback days (API calls required for historical data + news).
        """
    )

    parser.add_argument(
        "--tickers",
        nargs="+",
        default=["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "JPM", "BAC", "WMT"],
        help="List of ticker symbols to use for training (default: 10 major stocks)"
    )

    parser.add_argument(
        "--lookback-days",
        type=int,
        default=240,
        help="Number of historical days to collect per ticker (default: 240)"
    )

    parser.add_argument(
        "--horizon-days",
        type=int,
        default=21,
        help="Forward-looking horizon in days for labeling (default: 21)"
    )

    args = parser.parse_args()

    # Validate
    if len(args.tickers) < 2:
        print("❌ Error: At least 2 tickers required for training")
        sys.exit(1)

    if args.lookback_days < 100:
        print("❌ Error: lookback_days must be >= 100")
        sys.exit(1)

    if args.horizon_days < 5 or args.horizon_days > 90:
        print("❌ Error: horizon_days must be between 5 and 90")
        sys.exit(1)

    # Display configuration
    print("=" * 70)
    print("🧠 ML TRADE RECOMMENDER - MODEL TRAINING")
    print("=" * 70)
    print(f"\n📊 Configuration:")
    print(f"   Tickers: {', '.join(args.tickers)} ({len(args.tickers)} total)")
    print(f"   Lookback days: {args.lookback_days}")
    print(f"   Horizon days: {args.horizon_days}")
    print(f"   Model output: {MODEL_PATH}")
    print("\n" + "=" * 70)

    # Confirm
    response = input("\n🚀 Start training? (y/n): ").strip().lower()
    if response not in ["y", "yes"]:
        print("❌ Training cancelled")
        sys.exit(0)

    print("\n⏳ Training started... This may take several minutes.\n")

    try:
        # Train
        path = train_and_save(
            tickers=args.tickers,
            lookback_days=args.lookback_days,
            horizon_days=args.horizon_days
        )

        print("\n" + "=" * 70)
        print("✅ SUCCESS - Model trained and saved!")
        print("=" * 70)
        print(f"\n📁 Model saved to: {path}")
        print("\n📊 Model components:")
        print("   - Classifier: Logistic Regression (Buy/Sell/Hold predictions)")
        print("   - Regressor: Random Forest (Expected return forecasts)")
        print("\n💡 Next steps:")
        print("   1. Start your FastAPI server")
        print("   2. Test the model: GET /api/ml/recommend?ticker=AAPL")
        print("   3. Check status: GET /api/ml/status")
        print("\n" + "=" * 70)

    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ TRAINING FAILED")
        print("=" * 70)
        print(f"\n💥 Error: {e}")
        print("\n🔍 Common issues:")
        print("   - API rate limits (try fewer tickers or smaller lookback)")
        print("   - Network connectivity issues")
        print("   - Invalid ticker symbols")
        print("   - Insufficient historical data for some tickers")
        print("\n" + "=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()
