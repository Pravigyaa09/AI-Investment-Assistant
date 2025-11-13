import requests
import yfinance as yf
import pandas as pd
from datetime import date, timedelta
from tabulate import tabulate  # pip install tabulate

FINNHUB_API_KEY = "d43a56hr01qvk0jaulngd43a56hr01qvk0jaulo0"
TICKER = "AAPL"

results = {
    "Finnhub": {"News": "❌", "Price": "❌", "Sentiment": "❌"},
    "Yahoo": {"News": "❌", "Price": "❌", "Sentiment": "❌"},
    "Stooq": {"News": "❌", "Price": "❌", "Sentiment": "❌"},
}


def check_finnhub():
    print("\n🟦 Finnhub:")
    try:
        # --- NEWS ---
        to_date = date.today()
        from_date = to_date - timedelta(days=7)
        news_url = f"https://finnhub.io/api/v1/company-news?symbol={TICKER}&from={from_date}&to={to_date}&token={FINNHUB_API_KEY}"
        r = requests.get(news_url, timeout=10)
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            results["Finnhub"]["News"] = "✅"
            print("✅ Provides: Company News")
            print("   Example headline:", data[0].get("headline"))
        else:
            print("⚠️ No news data returned")

        # --- PRICE ---
        price_url = f"https://finnhub.io/api/v1/quote?symbol={TICKER}&token={FINNHUB_API_KEY}"
        p = requests.get(price_url, timeout=10)
        if "c" in p.json() and p.json()["c"]:
            results["Finnhub"]["Price"] = "✅"
            print("✅ Provides: Real-time Price Data")
        else:
            print("⚠️ Price data unavailable")

        # --- SENTIMENT ---
        sent_url = f"https://finnhub.io/api/v1/news-sentiment?symbol={TICKER}&token={FINNHUB_API_KEY}"
        s = requests.get(sent_url, timeout=10)
        if "sentiment" in s.text.lower():
            results["Finnhub"]["Sentiment"] = "✅"
            print("✅ Provides: Sentiment Data")
        else:
            print("⚠️ No sentiment data found")

    except Exception as e:
        print("❌ Finnhub error:", e)


def check_yahoo():
    print("\n🟨 Yahoo Finance:")
    try:
        ticker = yf.Ticker(TICKER)
        # --- NEWS ---
        news = getattr(ticker, "news", [])
        if news:
            results["Yahoo"]["News"] = "✅"
            print("✅ Provides: News")
            print("   Example headline:", news[0].get("title"))
        else:
            print("⚠️ No news available")

        # --- PRICE ---
        hist = ticker.history(period="5d")
        if not hist.empty:
            results["Yahoo"]["Price"] = "✅"
            print("✅ Provides: Historical Price Data")
            print("   Example closing price:", hist['Close'].iloc[-1])
        else:
            print("⚠️ No price data available")

    except Exception as e:
        print("❌ Yahoo Finance error:", e)


def check_stooq():
    print("\n🟥 Stooq:")
    try:
        url = f"https://stooq.pl/q/d/?s={TICKER.lower()}.us"
        tables = pd.read_html(url)
        if tables and not tables[0].empty:
            results["Stooq"]["Price"] = "✅"
            print("✅ Provides: Historical Price Data")
            print("   Example rows:", tables[0].head(2).to_dict(orient='records'))
        else:
            print("⚠️ No data tables found on Stooq")
    except Exception as e:
        print("❌ Stooq error:", e)


if __name__ == "__main__":
    print("🧠 Checking which data sources provide which data...\n")
    check_finnhub()
    check_yahoo()
    check_stooq()

    print("\n📊 Summary of Data Source Capabilities:\n")
    table = []
    for source, caps in results.items():
        table.append([source, caps["News"], caps["Price"], caps["Sentiment"]])

    print(tabulate(table, headers=["Source", "News", "Price", "Sentiment"], tablefmt="fancy_grid"))
    print("\n✅ Check complete.")
