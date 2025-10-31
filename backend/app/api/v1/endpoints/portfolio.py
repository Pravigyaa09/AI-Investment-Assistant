# backend/app/api/v1/endpoints/portfolio.py
"""Portfolio management endpoints - MongoDB version"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from bson import ObjectId

from app.db import get_repository, UserRepository, TradeRepository
from app.db.schemas import Portfolio, Holding, Trade, PyObjectId
from app.api.deps import get_current_user_mongo
from app.logger import get_logger

log = get_logger(__name__)
router = APIRouter()


# ========== UTILITY FUNCTIONS ==========

def convert_objectids_to_strings(obj):
    """Recursively convert ObjectIds to strings in any data structure"""
    if obj is None:
        return None
    elif isinstance(obj, (ObjectId, PyObjectId)):
        # Direct ObjectId or PyObjectId - convert to string
        return str(obj)
    elif hasattr(obj, '__dict__') and hasattr(obj, 'model_dump'):
        # Pydantic model - use model_dump and convert recursively
        return convert_objectids_to_strings(obj.model_dump())
    elif hasattr(obj, '__dict__'):
        # Regular object with __dict__ - convert to dict first
        try:
            obj_dict = vars(obj)
            return convert_objectids_to_strings(obj_dict)
        except TypeError:
            # If vars() fails and it looks like ObjectId, convert to string
            obj_type_str = str(type(obj))
            if any(x in obj_type_str.lower() for x in ['objectid', 'pyobjectid']):
                return str(obj)
            # For other types that can't be converted, return string representation
            return str(obj)
    elif isinstance(obj, dict):
        # Dictionary - process each key-value pair
        result = {}
        for key, value in obj.items():
            result[key] = convert_objectids_to_strings(value)
        return result
    elif isinstance(obj, (list, tuple)):
        # List or tuple - process each item
        return [convert_objectids_to_strings(item) for item in obj]
    else:
        # Check if it's an ObjectId type by checking the type string
        obj_type_str = str(type(obj))
        if any(x in obj_type_str.lower() for x in ['objectid', 'pyobjectid']):
            return str(obj)
        # Primitive type - return as is
        return obj


# ========== REQUEST/RESPONSE MODELS ==========

class TradeRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=16)
    side: str = Field(..., pattern="^(BUY|SELL)$")  # BUY or SELL
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0)


class PortfolioResponse(BaseModel):
    cash_balance: float
    holdings: List[dict]
    total_value: float
    total_pnl: float
    total_pnl_percent: float


@router.get("/portfolio", response_model=PortfolioResponse)
async def get_portfolio(
    current_user: dict = Depends(get_current_user_mongo)
):
    """Get current user's portfolio"""
    try:
        user_repo: UserRepository = get_repository(UserRepository)
        
        portfolio = await user_repo.get_portfolio(str(current_user["_id"]))
        if not portfolio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found"
            )
        
        # Calculate total P&L
        total_pnl = sum(h.pnl for h in portfolio.holdings)
        total_cost = sum(h.quantity * h.avg_cost for h in portfolio.holdings)
        total_pnl_percent = (total_pnl / total_cost * 100) if total_cost > 0 else 0
        
        # Convert holdings to safe dict format
        holdings_converted = convert_objectids_to_strings([h.model_dump() for h in portfolio.holdings])
        
        return PortfolioResponse(
            cash_balance=portfolio.cash_balance,
            holdings=holdings_converted,
            total_value=portfolio.total_value,
            total_pnl=total_pnl,
            total_pnl_percent=total_pnl_percent
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error fetching portfolio: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch portfolio"
        )



@router.get("/portfolio/trades")
async def get_trade_history(
    limit: int = 50,
    ticker: Optional[str] = None,
    current_user: dict = Depends(get_current_user_mongo)
):
    """Get user's trade history"""
    try:
        trade_repo: TradeRepository = get_repository(TradeRepository)
        
        if ticker:
            trades = await trade_repo.find_by_ticker(str(current_user["_id"]), ticker.upper())
        else:
            trades = await trade_repo.find_by_user(str(current_user["_id"]), limit)
        
        # Convert all ObjectIds to strings
        trades_converted = convert_objectids_to_strings(trades)
        
        return {
            "trades": trades_converted,
            "count": len(trades_converted) if trades_converted else 0
        }
        
    except Exception as e:
        log.error(f"Error fetching trade history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch trade history"
        )


@router.get("/portfolio/holdings/{ticker}")
async def get_holding_details(
    ticker: str,
    current_user: dict = Depends(get_current_user_mongo)
):
    """Get detailed information about a specific holding"""
    try:
        user_repo: UserRepository = get_repository(UserRepository)
        trade_repo: TradeRepository = get_repository(TradeRepository)
        
        portfolio = await user_repo.get_portfolio(str(current_user["_id"]))
        if not portfolio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found"
            )
        
        # Find the holding
        ticker_upper = ticker.upper()
        holding = None
        for h in portfolio.holdings:
            if h.ticker == ticker_upper:
                holding = h
                break
        
        if not holding:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Holding for {ticker_upper} not found"
            )
        
        # Get trade history for this ticker
        trades = await trade_repo.find_by_ticker(str(current_user["_id"]), ticker_upper)
        
        # Convert all ObjectIds to strings
        holding_dict = convert_objectids_to_strings(holding.model_dump())
        trades_converted = convert_objectids_to_strings(trades)
        
        return {
            "holding": holding_dict,
            "trades": trades_converted,
            "trade_count": len(trades_converted) if trades_converted else 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error fetching holding details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch holding details"
        )


@router.post("/portfolio/deposit")
async def deposit_cash(
    amount: float,
    current_user: dict = Depends(get_current_user_mongo)
):
    """Deposit cash into portfolio"""
    try:
        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amount must be positive"
            )
        
        user_repo: UserRepository = get_repository(UserRepository)
        
        portfolio = await user_repo.get_portfolio(str(current_user["_id"]))
        if not portfolio:
            portfolio = Portfolio(cash_balance=0)
        
        new_balance = portfolio.cash_balance + amount
        success = await user_repo.update_cash_balance(str(current_user["_id"]), new_balance)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update cash balance"
            )
        
        return {
            "message": "Cash deposited successfully",
            "amount_deposited": amount,
            "new_balance": new_balance
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error processing deposit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process deposit"
        )