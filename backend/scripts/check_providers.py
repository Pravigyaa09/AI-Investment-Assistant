# backend/scripts/check_providers.py
import sys, os
from pathlib import Path

# Make sure 'backend' package is importable (run from anywhere)
sys.path.append(str(Path(__file__).resolve().parents[1]))

# Load .env from project root
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except Exception:
    pass

from datetime import datetime, timedelta, timezone
from app.services.market_data import (
    debug_status,
    debug_clear_cache,
    get_candles_close,
    get_candles_rows_for_chart,
)

def main():
    print("== Provider status ==")
    print(debug_status())

    print("\n== Clear caches ==")
    print(debug_clear_cache())

    # Try chart rows (reports provider)
    ticker = "AAPL"
    days = 90
    dates, closes, provider = get_candles_rows_for_chart(ticker, days)
    print(f"\nChart rows for {ticker} days={days}: provider={provider} points={len(closes)}")
    if closes:
        print("  first:", dates[0], closes[0])
        print("  last :", dates[-1], closes[-1])

    # Try raw closes too
    closes2 = get_candles_close(ticker, days=60)
    print(f"\nCloses for {ticker}: n={len(closes2)} head={closes2[:3]} tail={closes2[-3:]}")

if __name__ == "__main__":
    main()
