# backend/app/db/mongo.py
"""MongoDB connection and database management - Fixed Version"""

from __future__ import annotations
import os
from typing import Optional
from contextlib import asynccontextmanager

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorDatabase,
    AsyncIOMotorCollection,
)
from bson import ObjectId
from app.core.config import settings

# Global client and database instances
_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


def _uri() -> str:
    """Get MongoDB URI from environment or settings"""
    return (
        os.getenv("MONGO_URI")
        or getattr(settings, "MONGO_URI", None)
        or "mongodb://127.0.0.1:27017"
    )


def _db_name() -> str:
    """Get database name from environment or settings"""
    return (
        os.getenv("MONGO_DB_NAME")
        or getattr(settings, "MONGO_DB_NAME", None)
        or "ai_invest"
    )


async def connect_to_mongo():
    """Initialize MongoDB connection"""
    global _client, _db
    
    uri = _uri()
    db_name = _db_name()
    
    _client = AsyncIOMotorClient(
        uri,
        maxPoolSize=10,
        minPoolSize=2,
        maxIdleTimeMS=60000,  # 60 seconds
    )
    _db = _client[db_name]
    
    # Verify connection
    await _client.server_info()
    print(f"Connected to MongoDB: {db_name}")
    
    # Create indexes
    await ensure_indexes(_db)


async def close_mongo_connection():
    """Close MongoDB connection"""
    global _client
    if _client is not None:  # Fixed: proper None check
        _client.close()
        print("Disconnected from MongoDB")


def get_client() -> AsyncIOMotorClient:
    """Get MongoDB client instance"""
    global _client
    if _client is None:
        # Auto-connect if not connected (for backwards compatibility)
        _client = AsyncIOMotorClient(_uri())
    return _client


def get_db() -> AsyncIOMotorDatabase:
    """Get MongoDB database instance"""
    global _db
    if _db is None:
        # Auto-connect if not connected (for backwards compatibility)
        client = get_client()
        _db = client[_db_name()]
    return _db


# Backward compatibility aliases
get_mongo_db = get_db
get_database = get_db


def get_collection(name: str) -> AsyncIOMotorCollection:
    """Get a specific collection"""
    return get_db()[name]


def to_object_id(value: str) -> ObjectId:
    """Convert string to ObjectId with validation"""
    try:
        return ObjectId(value)
    except Exception as e:
        raise ValueError(f"Invalid ObjectId: {value}") from e


async def ensure_indexes(db: Optional[AsyncIOMotorDatabase] = None) -> None:
    """Create all required indexes (idempotent)"""
    if db is None:
        db = get_db()
    
    try:
        # User indexes
        await db["users"].create_index("email", unique=True)
        await db["users"].create_index("username")
        
        # Trade indexes
        await db["trades"].create_index([("user_id", 1), ("created_at", -1)])
        await db["trades"].create_index([("user_id", 1), ("ticker", 1)])
        await db["trades"].create_index("ticker")
        
        # AI Score indexes
        await db["ai_scores"].create_index([("user_id", 1), ("ticker", 1)])
        await db["ai_scores"].create_index([("user_id", 1), ("expires_at", 1)])
        
        # Recommendation indexes
        await db["recommendations"].create_index([("user_id", 1), ("is_active", 1)])
        await db["recommendations"].create_index([("user_id", 1), ("ticker", 1)])
        
        # Market data indexes
        await db["market_data"].create_index("ticker", unique=True)
        await db["market_data"].create_index("last_updated")
        
        print("MongoDB indexes created/verified successfully")
    except Exception as e:
        print(f"Warning: Some indexes may not have been created: {e}")


@asynccontextmanager
async def get_mongo_session():
    """Get MongoDB session for transactions"""
    client = get_client()
    async with await client.start_session() as session:
        async with session.start_transaction():
            yield session


# Repository instances (singleton pattern)
_repositories = {}


def get_repository(repo_class):
    """Get or create repository instance"""
    class_name = repo_class.__name__
    
    if class_name not in _repositories:
        from app.db.repositories import (
            UserRepository, TradeRepository, AIScoreRepository,
            RecommendationRepository, MarketDataRepository
        )
        
        db = get_db()
        
        # Map class to instance
        if class_name == "UserRepository":
            _repositories[class_name] = UserRepository(db)
        elif class_name == "TradeRepository":
            _repositories[class_name] = TradeRepository(db)
        elif class_name == "AIScoreRepository":
            _repositories[class_name] = AIScoreRepository(db)
        elif class_name == "RecommendationRepository":
            _repositories[class_name] = RecommendationRepository(db)
        elif class_name == "MarketDataRepository":
            _repositories[class_name] = MarketDataRepository(db)
        else:
            raise ValueError(f"Unknown repository class: {class_name}")
    
    return _repositories[class_name]