# backend/app/api/v1/endpoints/portfolio.py
"""Portfolio management endpoints - MongoDB version"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.db import get_repository, UserRepository, TradeRepository
from app.db.schemas import Portfolio, Holding, Trade
from app.api.deps import get_current_user


router = APIRouter()


class TradeRequest(BaseModel):
    ticker: str
    side: str  # BUY or SELL
    quantity: float
    price: float


class PortfolioResponse(BaseModel):
    cash_balance: float
    holdings: List[dict]
    total_value: float
    total_pnl: float
    total_pnl_percent: float


@router.get("/portfolio", response_model=PortfolioResponse)
async def get_portfolio(
    current_user: dict = Depends(get_current_user)
):
    """Get current user's portfolio"""
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
    
    return PortfolioResponse(
        cash_balance=portfolio.cash_balance,
        holdings=[h.model_dump() for h in portfolio.holdings],
        total_value=portfolio.total_value,
        total_pnl=total_pnl,
        total_pnl_percent=total_pnl_percent
    )


@router.post("/portfolio/trade")
async def execute_trade(
    trade_request: TradeRequest,
    current_user: dict = Depends(get_current_user)
):
    """Execute a buy or sell trade"""
    user_repo: UserRepository = get_repository(UserRepository)
    trade_repo: TradeRepository = get_repository(TradeRepository)
    
    # Validate trade side
    if trade_request.side not in ["BUY", "SELL"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Side must be BUY or SELL"
        )
    
    # Create trade object
    trade = Trade(
        user_id=current_user["_id"],
        ticker=trade_request.ticker,
        side=trade_request.side,
        quantity=trade_request.quantity,
        price=trade_request.price,
        commission=trade_request.quantity * trade_request.price * 0.001  # 0.1% commission
    )
    
    # Execute trade
    trade_id = await trade_repo.execute_trade(trade, user_repo)
    
    if not trade_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trade execution failed. Check your balance or holdings."
        )
    
    return {
        "message": f"{trade_request.side} order executed successfully",
        "trade_id": trade_id,
        "ticker": trade_request.ticker,
        "quantity": trade_request.quantity,
        "price": trade_request.price,
        "total_value": trade.total_value
    }


@router.get("/portfolio/trades")
async def get_trade_history(
    limit: int = 50,
    ticker: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get user's trade history"""
    trade_repo: TradeRepository = get_repository(TradeRepository)
    
    if ticker:
        trades = await trade_repo.find_by_ticker(str(current_user["_id"]), ticker)
    else:
        trades = await trade_repo.find_by_user(str(current_user["_id"]), limit)
    
    return {
        "trades": trades,
        "count": len(trades)
    }


@router.get("/portfolio/holdings/{ticker}")
async def get_holding_details(
    ticker: str,
    current_user: dict = Depends(get_current_user)
):
    """Get detailed information about a specific holding"""
    user_repo: UserRepository = get_repository(UserRepository)
    trade_repo: TradeRepository = get_repository(TradeRepository)
    
    portfolio = await user_repo.get_portfolio(str(current_user["_id"]))
    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found"
        )
    
    # Find the holding
    holding = None
    for h in portfolio.holdings:
        if h.ticker == ticker:
            holding = h
            break
    
    if not holding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Holding for {ticker} not found"
        )
    
    # Get trade history for this ticker
    trades = await trade_repo.find_by_ticker(str(current_user["_id"]), ticker)
    
    return {
        "holding": holding.model_dump(),
        "trades": trades,
        "trade_count": len(trades)
    }


@router.post("/portfolio/deposit")
async def deposit_cash(
    amount: float,
    current_user: dict = Depends(get_current_user)
):
    """Deposit cash into portfolio"""
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