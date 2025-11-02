# backend/app/services/stock_categories.py
"""
Stock category definitions for news filtering
"""
from typing import Dict, List

STOCK_CATEGORIES: Dict[str, Dict[str, List[str]]] = {
    "technology": {
        "name": "Technology",
        "tickers": ["AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "INTC", "ORCL", "ADBE", "CRM", "CSCO", "IBM", "QCOM", "AVGO", "TXN"]
    },
    "currency": {
        "name": "Currency & Fintech",
        "tickers": ["COIN", "SQ", "PYPL", "AFRM", "SOFI", "NU", "HOOD", "MARA", "RIOT", "MSTR"]
    },
    "b2b": {
        "name": "B2B Services",
        "tickers": ["SNOW", "PLTR", "DDOG", "NET", "ZS", "OKTA", "CRWD", "S", "WDAY", "NOW", "TEAM", "ZM", "DOCN", "FROG", "BILL"]
    },
    "clothing": {
        "name": "Clothing & Fashion",
        "tickers": ["NKE", "LULU", "ADDYY", "TPR", "RL", "UAA", "VFC", "HBI", "GOOS", "ONON", "CROX", "BIRK", "CPRI"]
    },
    "consumer": {
        "name": "Consumer Goods",
        "tickers": ["AMZN", "WMT", "TGT", "COST", "HD", "LOW", "DG", "DLTR", "BBY", "FIVE", "BURL"]
    },
    "automotive": {
        "name": "Automotive",
        "tickers": ["TSLA", "F", "GM", "RIVN", "LCID", "NIO", "XPEV", "LI", "TM", "HMC", "RACE", "STLA"]
    },
    "healthcare": {
        "name": "Healthcare & Biotech",
        "tickers": ["JNJ", "UNH", "PFE", "ABBV", "TMO", "MRNA", "LLY", "GILD", "AMGN", "CVS", "CI", "HUM", "BIIB"]
    },
    "finance": {
        "name": "Finance & Banking",
        "tickers": ["JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "SCHW", "AXP", "V", "MA", "COF", "USB"]
    },
    "energy": {
        "name": "Energy & Utilities",
        "tickers": ["XOM", "CVX", "COP", "SLB", "EOG", "PXD", "MPC", "VLO", "PSX", "OXY", "HAL", "DVN", "FANG"]
    },
    "entertainment": {
        "name": "Entertainment & Media",
        "tickers": ["DIS", "NFLX", "PARA", "WBD", "SPOT", "RBLX", "EA", "TTWO", "ATVI", "U", "LYV", "FOXA"]
    },
    "food": {
        "name": "Food & Beverage",
        "tickers": ["MCD", "SBUX", "CMG", "YUM", "QSR", "DPZ", "WEN", "JACK", "PZZA", "DNKN", "KO", "PEP", "MNST"]
    },
    "realestate": {
        "name": "Real Estate",
        "tickers": ["Z", "RDFN", "OPEN", "COMP", "EXPI", "CBRE", "JLL", "AMT", "PLD", "SPG", "O", "WELL"]
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
