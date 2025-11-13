# backend/app/services/stock_categories.py
"""
Stock category definitions for news filtering
"""
from typing import Dict, List

STOCK_CATEGORIES: Dict[str, Dict[str, List[str]]] = {
    "technology": {
        "name": "Technology",
        "tickers": ["AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "INTC"]
    },
    "currency": {
        "name": "Currency & Fintech",
        "tickers": ["COIN", "SQ", "PYPL", "AFRM", "SOFI", "NU"]
    },
    "b2b": {
        "name": "B2B Services",
        "tickers": ["SNOW", "PLTR", "DDOG", "NET", "ZS"]
    },
    "clothing": {
        "name": "Clothing & Fashion",
        "tickers": ["NKE", "LULU", "ADDYY", "TPR", "RL"]
    },
    "consumer": {
        "name": "Consumer Goods",
        "tickers": ["AMZN", "WMT", "TGT", "COST", "HD"]
    },
    "automotive": {
        "name": "Automotive",
        "tickers": ["TSLA", "F", "GM", "RIVN", "LCID"]
    },
    "healthcare": {
        "name": "Healthcare & Biotech",
        "tickers": ["JNJ", "UNH", "PFE", "ABBV", "TMO"]
    },
    "finance": {
        "name": "Finance & Banking",
        "tickers": ["JPM", "BAC", "WFC", "GS", "MS"]
    },
    "energy": {
        "name": "Energy & Utilities",
        "tickers": ["XOM", "CVX", "COP", "SLB", "EOG"]
    },
    "entertainment": {
        "name": "Entertainment & Media",
        "tickers": ["DIS", "NFLX", "PARA", "WBD", "SPOT"]
    },
    "food": {
        "name": "Food & Beverage",
        "tickers": ["MCD", "SBUX", "CMG", "YUM", "QSR"]
    },
    "realestate": {
        "name": "Real Estate",
        "tickers": ["Z", "RDFN", "OPEN", "COMP", "EXPI"]
    }
}

def get_all_categories() -> Dict[str, str]:
    """Get all category keys and names"""
    return {key: data["name"] for key, data in STOCK_CATEGORIES.items()}

def get_category_tickers(category: str) -> List[str]:
    """Get tickers for a specific category"""
    return STOCK_CATEGORIES.get(category, {}).get("tickers", [])

def get_ticker_categories(ticker: str) -> List[str]:
    """Find which categories a ticker belongs to"""
    ticker = ticker.upper()
    categories = []
    for cat_key, cat_data in STOCK_CATEGORIES.items():
        if ticker in cat_data["tickers"]:
            categories.append(cat_key)
    return categories
