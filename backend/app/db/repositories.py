# backend/app/db/repositories.py
"""Repository pattern for MongoDB operations"""

from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection

from app.db.schemas import (
    User, Portfolio, Holding, Trade, 
    AIScore, Recommendation, MarketData
)


class BaseRepository:
    """Base repository with common CRUD operations"""
    
    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str):
        self.db = db
        self.collection: AsyncIOMotorCollection = db[collection_name]
    
    async def create(self, document: dict) -> str:
        """Create a new document"""
        result = await self.collection.insert_one(document)
        return str(result.inserted_id)
    
    async def find_by_id(self, id: str) -> Optional[dict]:
        """Find document by ID"""
        return await self.collection.find_one({"_id": ObjectId(id)})
    
    async def find_one(self, filter: dict) -> Optional[dict]:
        """Find single document by filter"""
        return await self.collection.find_one(filter)
    
    async def find_many(self, filter: dict, limit: int = 100) -> List[dict]:
        """Find multiple documents"""
        cursor = self.collection.find(filter).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def update_one(self, id: str, update: dict) -> bool:
        """Update document by ID"""
        update["updated_at"] = datetime.now(timezone.utc)
        result = await self.collection.update_one(
            {"_id": ObjectId(id)},
            {"$set": update}
        )
        return result.modified_count > 0
    
    async def delete_one(self, id: str) -> bool:
        """Delete document by ID"""
        result = await self.collection.delete_one({"_id": ObjectId(id)})
        return result.deleted_count > 0


class UserRepository(BaseRepository):
    """User-specific repository operations"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "users")
    
    async def find_by_email(self, email: str) -> Optional[dict]:
        """Find user by email"""
        return await self.find_one({"email": email})
    
    async def update_portfolio(self, user_id: str, portfolio: Portfolio) -> bool:
        """Update user's portfolio"""
        return await self.update_one(user_id, {"portfolio": portfolio.model_dump()})
    
    async def get_portfolio(self, user_id: str) -> Optional[Portfolio]:
        """Get user's portfolio"""
        user = await self.find_by_id(user_id)
        if user and "portfolio" in user:
            return Portfolio(**user["portfolio"])
        return None
    
    async def update_holding(self, user_id: str, ticker: str, holding: Holding) -> bool:
        """Update or add a specific holding"""
        user = await self.find_by_id(user_id)
        if not user:
            return False
        
        portfolio = Portfolio(**user.get("portfolio", {}))
        
        # Find and update or append
        holding_found = False
        for i, h in enumerate(portfolio.holdings):
            if h.ticker == ticker:
                portfolio.holdings[i] = holding
                holding_found = True
                break
        
        if not holding_found:
            portfolio.holdings.append(holding)
        
        # Update portfolio totals
        portfolio.total_value = portfolio.cash_balance + sum(
            h.current_value for h in portfolio.holdings
        )
        portfolio.last_updated = datetime.now(timezone.utc)
        
        return await self.update_portfolio(user_id, portfolio)
    
    async def remove_holding(self, user_id: str, ticker: str) -> bool:
        """Remove a holding from portfolio"""
        result = await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$pull": {"portfolio.holdings": {"ticker": ticker}}}
        )
        return result.modified_count > 0
    
    async def update_cash_balance(self, user_id: str, amount: float) -> bool:
        """Update cash balance"""
        return await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "portfolio.cash_balance": amount,
                    "portfolio.last_updated": datetime.now(timezone.utc)
                }
            }
        ).modified_count > 0


class TradeRepository(BaseRepository):
    """Trade-specific repository operations"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "trades")
    
    async def find_by_user(self, user_id: str, limit: int = 100) -> List[dict]:
        """Find all trades for a user"""
        return await self.find_many({"user_id": ObjectId(user_id)}, limit)
    
    async def find_by_ticker(self, user_id: str, ticker: str) -> List[dict]:
        """Find trades for a specific ticker"""
        return await self.find_many({
            "user_id": ObjectId(user_id),
            "ticker": ticker
        })
    
    async def execute_trade(self, trade: Trade, user_repo: UserRepository) -> Optional[str]:
        """Execute a trade and update portfolio"""
        # Calculate total value
        trade.total_value = trade.calculate_total()
        
        # Get user portfolio
        portfolio = await user_repo.get_portfolio(str(trade.user_id))
        if not portfolio:
            return None
        
        # Check if user has enough cash for BUY
        if trade.side == "BUY" and portfolio.cash_balance < trade.total_value:
            return None  # Insufficient funds
        
        # Find existing holding
        holding = None
        holding_index = -1
        for i, h in enumerate(portfolio.holdings):
            if h.ticker == trade.ticker:
                holding = h
                holding_index = i
                break
        
        if trade.side == "BUY":
            # Update or create holding
            if holding:
                # Update existing holding
                new_quantity = holding.quantity + trade.quantity
                new_total_cost = (holding.quantity * holding.avg_cost) + trade.total_value
                holding.quantity = new_quantity
                holding.avg_cost = new_total_cost / new_quantity
                holding.last_price = trade.price
                holding.current_value = new_quantity * trade.price
                holding.updated_at = datetime.now(timezone.utc)
            else:
                # Create new holding
                holding = Holding(
                    ticker=trade.ticker,
                    quantity=trade.quantity,
                    avg_cost=trade.price,
                    last_price=trade.price,
                    current_value=trade.quantity * trade.price
                )
                portfolio.holdings.append(holding)
            
            # Deduct cash
            portfolio.cash_balance -= trade.total_value
            
        else:  # SELL
            if not holding or holding.quantity < trade.quantity:
                return None  # Insufficient shares
            
            # Update holding
            holding.quantity -= trade.quantity
            if holding.quantity == 0:
                # Remove holding if quantity is 0
                portfolio.holdings.pop(holding_index)
            else:
                holding.current_value = holding.quantity * trade.price
                holding.last_price = trade.price
                holding.updated_at = datetime.now(timezone.utc)
            
            # Add cash
            portfolio.cash_balance += trade.total_value
        
        # Update portfolio
        portfolio.total_value = portfolio.cash_balance + sum(
            h.current_value for h in portfolio.holdings
        )
        portfolio.last_updated = datetime.now(timezone.utc)
        
        # Save trade
        trade_id = await self.create(trade.model_dump(by_alias=True))
        
        # Update user portfolio
        await user_repo.update_portfolio(str(trade.user_id), portfolio)
        
        return trade_id


class AIScoreRepository(BaseRepository):
    """AI Score repository operations"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "ai_scores")
    
    async def find_latest(self, user_id: str, ticker: str) -> Optional[dict]:
        """Find latest score for user and ticker"""
        return await self.collection.find_one(
            {
                "user_id": ObjectId(user_id),
                "ticker": ticker,
                "expires_at": {"$gt": datetime.now(timezone.utc)}
            },
            sort=[("created_at", -1)]
        )
    
    async def find_user_scores(self, user_id: str) -> List[dict]:
        """Find all active scores for a user"""
        return await self.find_many({
            "user_id": ObjectId(user_id),
            "expires_at": {"$gt": datetime.now(timezone.utc)}
        })


class RecommendationRepository(BaseRepository):
    """Recommendation repository operations"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "recommendations")
    
    async def find_active(self, user_id: str) -> List[dict]:
        """Find active recommendations for user"""
        return await self.find_many({
            "user_id": ObjectId(user_id),
            "is_active": True,
            "valid_until": {"$gt": datetime.now(timezone.utc)}
        })
    
    async def deactivate_old(self, user_id: str, ticker: str) -> bool:
        """Deactivate old recommendations for a ticker"""
        result = await self.collection.update_many(
            {"user_id": ObjectId(user_id), "ticker": ticker},
            {"$set": {"is_active": False}}
        )
        return result.modified_count > 0


class MarketDataRepository(BaseRepository):
    """Market data cache repository"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "market_data")
    
    async def find_by_ticker(self, ticker: str) -> Optional[dict]:
        """Find market data by ticker"""
        return await self.find_one({"ticker": ticker})
    
    async def upsert(self, ticker: str, data: dict) -> bool:
        """Update or insert market data"""
        data["last_updated"] = datetime.now(timezone.utc)
        result = await self.collection.update_one(
            {"ticker": ticker},
            {"$set": data},
            upsert=True
        )
        return result.modified_count > 0 or result.upserted_id is not None