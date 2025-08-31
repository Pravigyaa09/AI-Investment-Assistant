# backend/app/db/migrate_to_mongo.py
"""Initialize MongoDB with sample data since SQLAlchemy has no data"""

import asyncio
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import json

from app.core.config import settings
from app.logger import get_logger

log = get_logger(__name__)


async def initialize_mongodb():
    """Initialize MongoDB with sample data for testing"""
    
    print("=" * 60)
    print("Initializing MongoDB Database")
    print("=" * 60)
    
    # Setup MongoDB connection
    try:
        mongo_client = AsyncIOMotorClient(settings.MONGO_URI)
        mongo_db = mongo_client[settings.MONGO_DB_NAME]
        await mongo_client.server_info()  # Test connection
        print("✓ Connected to MongoDB")
    except Exception as e:
        print(f"✗ Failed to connect to MongoDB: {e}")
        print("Make sure MongoDB is running and MONGO_URI is set in your .env file")
        return
    
    try:
        # Clear existing data (optional - comment out if you want to keep existing data)
        print("\n--- Clearing existing data ---")
        await mongo_db.users.delete_many({})
        await mongo_db.trades.delete_many({})
        await mongo_db.ai_scores.delete_many({})
        await mongo_db.recommendations.delete_many({})
        await mongo_db.market_data.delete_many({})
        print("✓ Cleared existing collections")
        
        # Step 1: Create sample users
        print("\n--- Creating Sample Users ---")
        
        # User 1: Demo user with portfolio
        user1_id = ObjectId()
        user1 = {
            "_id": user1_id,
            "email": "demo@aiinvest.com",
            "username": "demo_user",
            "hashed_password": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY3pjVNkS0tBkF.",  # password: demo123
            "is_active": True,
            "is_verified": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "portfolio": {
                "cash_balance": 25000.0,
                "holdings": [
                    {
                        "ticker": "AAPL",
                        "quantity": 100,
                        "avg_cost": 150.0,
                        "last_price": 175.0,
                        "current_value": 17500.0,
                        "pnl": 2500.0,
                        "pnl_percent": 16.67,
                        "updated_at": datetime.now(timezone.utc)
                    },
                    {
                        "ticker": "GOOGL",
                        "quantity": 50,
                        "avg_cost": 120.0,
                        "last_price": 140.0,
                        "current_value": 7000.0,
                        "pnl": 1000.0,
                        "pnl_percent": 16.67,
                        "updated_at": datetime.now(timezone.utc)
                    },
                    {
                        "ticker": "MSFT",
                        "quantity": 75,
                        "avg_cost": 300.0,
                        "last_price": 380.0,
                        "current_value": 28500.0,
                        "pnl": 6000.0,
                        "pnl_percent": 26.67,
                        "updated_at": datetime.now(timezone.utc)
                    }
                ],
                "total_value": 78000.0,  # 25000 cash + 53000 holdings
                "last_updated": datetime.now(timezone.utc)
            }
        }
        
        # User 2: New user with just cash
        user2_id = ObjectId()
        user2 = {
            "_id": user2_id,
            "email": "newuser@aiinvest.com",
            "username": "new_investor",
            "hashed_password": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY3pjVNkS0tBkF.",  # password: demo123
            "is_active": True,
            "is_verified": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "portfolio": {
                "cash_balance": 50000.0,
                "holdings": [],
                "total_value": 50000.0,
                "last_updated": datetime.now(timezone.utc)
            }
        }
        
        # User 3: Test user
        user3_id = ObjectId()
        user3 = {
            "_id": user3_id,
            "email": "test@aiinvest.com",
            "username": "test_user",
            "hashed_password": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY3pjVNkS0tBkF.",  # password: demo123
            "is_active": True,
            "is_verified": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "portfolio": {
                "cash_balance": 10000.0,
                "holdings": [],
                "total_value": 10000.0,
                "last_updated": datetime.now(timezone.utc)
            }
        }
        
        await mongo_db.users.insert_many([user1, user2, user3])
        print("✓ Created 3 sample users")
        
        # Step 2: Create sample trades for demo user
        print("\n--- Creating Sample Trades ---")
        
        trades = [
            {
                "_id": ObjectId(),
                "user_id": user1_id,
                "ticker": "AAPL",
                "side": "BUY",
                "quantity": 100,
                "price": 150.0,
                "total_value": 15000.0,
                "commission": 15.0,
                "status": "EXECUTED",
                "executed_at": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            },
            {
                "_id": ObjectId(),
                "user_id": user1_id,
                "ticker": "GOOGL",
                "side": "BUY",
                "quantity": 50,
                "price": 120.0,
                "total_value": 6000.0,
                "commission": 6.0,
                "status": "EXECUTED",
                "executed_at": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            },
            {
                "_id": ObjectId(),
                "user_id": user1_id,
                "ticker": "MSFT",
                "side": "BUY",
                "quantity": 75,
                "price": 300.0,
                "total_value": 22500.0,
                "commission": 22.5,
                "status": "EXECUTED",
                "executed_at": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
        ]
        
        await mongo_db.trades.insert_many(trades)
        print("✓ Created sample trades")
        
        # Step 3: Create sample market data
        print("\n--- Creating Sample Market Data ---")
        
        market_data = [
            {
                "_id": ObjectId(),
                "ticker": "AAPL",
                "current_price": 175.0,
                "open_price": 172.0,
                "high": 176.5,
                "low": 171.5,
                "close": 175.0,
                "volume": 50000000,
                "change": 3.0,
                "change_percent": 1.74,
                "market_cap": 2800000000000,
                "pe_ratio": 29.5,
                "dividend_yield": 0.5,
                "source": "yahoo_finance",
                "last_updated": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            },
            {
                "_id": ObjectId(),
                "ticker": "GOOGL",
                "current_price": 140.0,
                "open_price": 138.0,
                "high": 141.0,
                "low": 137.5,
                "close": 140.0,
                "volume": 25000000,
                "change": 2.0,
                "change_percent": 1.45,
                "market_cap": 1800000000000,
                "pe_ratio": 25.3,
                "dividend_yield": 0.0,
                "source": "yahoo_finance",
                "last_updated": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            },
            {
                "_id": ObjectId(),
                "ticker": "MSFT",
                "current_price": 380.0,
                "open_price": 375.0,
                "high": 382.0,
                "low": 374.0,
                "close": 380.0,
                "volume": 30000000,
                "change": 5.0,
                "change_percent": 1.33,
                "market_cap": 2850000000000,
                "pe_ratio": 32.1,
                "dividend_yield": 0.7,
                "source": "yahoo_finance",
                "last_updated": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
        ]
        
        await mongo_db.market_data.insert_many(market_data)
        print("✓ Created sample market data")
        
        # Step 4: Create indexes
        print("\n--- Creating MongoDB Indexes ---")
        from app.db.mongo import ensure_indexes
        await ensure_indexes(mongo_db)
        print("✓ Indexes created successfully")
        
        # Step 5: Save initialization info
        print("\n--- Saving Initialization Info ---")
        init_info = {
            "initialization_date": datetime.now(timezone.utc).isoformat(),
            "users_created": [
                {"email": "demo@aiinvest.com", "password": "demo123", "has_portfolio": True},
                {"email": "newuser@aiinvest.com", "password": "demo123", "has_portfolio": False},
                {"email": "test@aiinvest.com", "password": "demo123", "has_portfolio": False}
            ],
            "collections_initialized": ["users", "trades", "market_data"]
        }
        
        with open("mongodb_init_info.json", "w") as f:
            json.dump(init_info, f, indent=2, default=str)
        
        print("\n" + "=" * 60)
        print("✓ MongoDB Initialization Complete!")
        print("=" * 60)
        print("\n📝 Login Credentials:")
        print("  Email: demo@aiinvest.com")
        print("  Password: demo123")
        print("\n  Email: newuser@aiinvest.com")
        print("  Password: demo123")
        print("\n  Email: test@aiinvest.com")
        print("  Password: demo123")
        print("\n✅ You can now start using the application!")
        
    except Exception as e:
        print(f"\n✗ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        mongo_client.close()


async def verify_initialization():
    """Verify MongoDB initialization"""
    
    print("\n" + "=" * 60)
    print("Verification Report")
    print("=" * 60)
    
    mongo_client = AsyncIOMotorClient(settings.MONGO_URI)
    mongo_db = mongo_client[settings.MONGO_DB_NAME]
    
    try:
        # Count documents
        users_count = await mongo_db.users.count_documents({})
        trades_count = await mongo_db.trades.count_documents({})
        market_data_count = await mongo_db.market_data.count_documents({})
        
        print(f"\n📊 Database Statistics:")
        print(f"  Users: {users_count}")
        print(f"  Trades: {trades_count}")
        print(f"  Market Data: {market_data_count}")
        
        # Show user details
        print(f"\n👤 Users in Database:")
        async for user in mongo_db.users.find({}, {"email": 1, "username": 1, "portfolio.total_value": 1}):
            print(f"  - {user['email']} ({user['username']}): ${user['portfolio']['total_value']:,.2f}")
        
        print("\n✓ Verification complete!")
        
    finally:
        mongo_client.close()


if __name__ == "__main__":
    # Check MongoDB settings
    if not hasattr(settings, 'MONGO_URI') or not settings.MONGO_URI:
        print("ERROR: MONGO_URI not found in settings.")
        print("Please ensure your .env file contains:")
        print("  MONGO_URI=mongodb://localhost:27017")
        print("  MONGO_DB_NAME=ai_invest")
        exit(1)
    
    print("MongoDB URI:", settings.MONGO_URI)
    print("Database Name:", settings.MONGO_DB_NAME)
    
    # Run initialization
    asyncio.run(initialize_mongodb())
    
    # Verify
    asyncio.run(verify_initialization())