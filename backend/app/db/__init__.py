# backend/app/db/__init__.py
"""Database package - MongoDB only architecture"""

from .mongo import (
    connect_to_mongo,
    close_mongo_connection,
    get_db,
    get_client,
    get_collection,
    to_object_id,
    get_repository,
    get_mongo_session
)

from .schemas import (
    User,
    Portfolio,
    Holding,
    Trade,
    AIScore,
    Recommendation,
    MarketData,
    PyObjectId,
    MongoBaseModel
)

from .repositories import (
    BaseRepository,
    UserRepository,
    TradeRepository,
    AIScoreRepository,
    RecommendationRepository,
    MarketDataRepository
)

__all__ = [
    # Connection management
    "connect_to_mongo",
    "close_mongo_connection",
    "get_db",
    "get_client",
    "get_collection",
    "to_object_id",
    "get_repository",
    "get_mongo_session",
    
    # Schemas
    "User",
    "Portfolio",
    "Holding",
    "Trade",
    "AIScore",
    "Recommendation",
    "MarketData",
    "PyObjectId",
    "MongoBaseModel",
    
    # Repositories
    "BaseRepository",
    "UserRepository",
    "TradeRepository",
    "AIScoreRepository",
    "RecommendationRepository",
    "MarketDataRepository",
]