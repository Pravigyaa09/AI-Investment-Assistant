# backend/app/models/__init__.py
"""
Models package - MongoDB schemas only
All SQLAlchemy models have been removed in favor of MongoDB
"""

# Import MongoDB schemas if needed
from app.db.schemas import (
    User,
    Portfolio,
    Holding,
    Trade,
    AIScore,
    Recommendation,
    MarketData
)

__all__ = [
    "User",
    "Portfolio", 
    "Holding",
    "Trade",
    "AIScore",
    "Recommendation",
    "MarketData"
]