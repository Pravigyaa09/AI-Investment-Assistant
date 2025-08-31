# backend/app/routers/mongo_portfolio_v2.py
"""MongoDB-based portfolio management endpoints - Version 2"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field

from app.db import (
    get_repository,
    UserRepository,
    TradeRepository,
    AIScoreRepository,
    RecommendationRepository,
    MarketDataRepository
)
from app.db.schemas import Portfolio, Holding, Trade, PyObjectId
from app.api.deps import get_current_user_mongo  # You'll need to create this
from app.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/portfolio", tags=["Portfolio"])


# ========== REQUEST/RESPONSE MODELS ==========

class TradeRequest(BaseModel):
    """Request model for executing trades"""
    ticker: str = Field(..., min_length=1, max_length=16)
    side: str = Field(..., pattern="^(BUY|SELL)$")
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    order_type: str = Field(default="MARKET", pattern="^(MARKET|LIMIT)$")


class DepositRequest(BaseModel):
    """Request model for cash deposits"""
    amount: float = Field(..., gt=0)
    method: str = Field(default="BANK_TRANSFER")


class HoldingResponse(BaseModel):
    """Response model for individual holdings"""
    ticker: str
    quantity: float
    avg_cost: float
    last_price: float
    current_value: float
    pnl: float
    pnl_percent: float
    weight: float  # Portfolio weight percentage


class PortfolioResponse(BaseModel):
    """Response model for portfolio summary"""
    cash_balance: float
    holdings: List[HoldingResponse]
    total_value: float
    total_invested: float
    total_pnl: float
    total_pnl_percent: float
    holdings_count: int
    last_updated: datetime


class TradeResponse(BaseModel):
    """Response model for trade execution"""
    trade_id: str
    ticker: str
    side: str
    quantity: float
    price: float
    total_value: float
    commission: float
    executed_at: datetime
    message: str


class PerformanceMetrics(BaseModel):
    """Performance metrics for portfolio"""
    total_return: float
    total_return_percent: float
    best_performer: Optional[Dict[str, Any]]
    worst_performer: Optional[Dict[str, Any]]
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    sharpe_ratio: Optional[float]


# ========== PORTFOLIO ENDPOINTS ==========

@router.get("", response_model=PortfolioResponse)
async def get_portfolio(
    current_user: dict = Depends(get_current_user_mongo)
):
    """Get current user's portfolio with detailed metrics"""
    try:
        user_repo: UserRepository = get_repository(UserRepository)
        
        portfolio = await user_repo.get_portfolio(str(current_user["_id"]))
        if not portfolio:
            # Initialize empty portfolio for new users
            portfolio = Portfolio()
            await user_repo.update_portfolio(str(current_user["_id"]), portfolio)
        
        # Calculate metrics
        total_invested = sum(h.quantity * h.avg_cost for h in portfolio.holdings)
        total_current = sum(h.current_value for h in portfolio.holdings)
        total_pnl = total_current - total_invested if total_invested > 0 else 0
        total_pnl_percent = (total_pnl / total_invested * 100) if total_invested > 0 else 0
        
        # Calculate portfolio weights
        holdings_response = []
        for holding in portfolio.holdings:
            weight = (holding.current_value / portfolio.total_value * 100) if portfolio.total_value > 0 else 0
            holdings_response.append(
                HoldingResponse(
                    ticker=holding.ticker,
                    quantity=holding.quantity,
                    avg_cost=holding.avg_cost,
                    last_price=holding.last_price,
                    current_value=holding.current_value,
                    pnl=holding.pnl,
                    pnl_percent=holding.pnl_percent,
                    weight=weight
                )
            )
        
        return PortfolioResponse(
            cash_balance=portfolio.cash_balance,
            holdings=holdings_response,
            total_value=portfolio.total_value,
            total_invested=total_invested,
            total_pnl=total_pnl,
            total_pnl_percent=total_pnl_percent,
            holdings_count=len(portfolio.holdings),
            last_updated=portfolio.last_updated
        )
        
    except Exception as e:
        log.error(f"Error fetching portfolio: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch portfolio"
        )


@router.post("/trade", response_model=TradeResponse)
async def execute_trade(
    trade_request: TradeRequest,
    current_user: dict = Depends(get_current_user_mongo)
):
    """Execute a buy or sell trade"""
    try:
        user_repo: UserRepository = get_repository(UserRepository)
        trade_repo: TradeRepository = get_repository(TradeRepository)
        
        # Create trade object
        trade = Trade(
            user_id=PyObjectId(str(current_user["_id"])),
            ticker=trade_request.ticker.upper(),
            side=trade_request.side,
            quantity=trade_request.quantity,
            price=trade_request.price,
            commission=trade_request.quantity * trade_request.price * 0.001  # 0.1% commission
        )
        
        # Execute trade
        trade_id = await trade_repo.execute_trade(trade, user_repo)
        
        if not trade_id:
            if trade.side == "BUY":
                detail = "Insufficient funds for this trade"
            else:
                detail = "Insufficient shares to sell"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=detail
            )
        
        return TradeResponse(
            trade_id=trade_id,
            ticker=trade.ticker,
            side=trade.side,
            quantity=trade.quantity,
            price=trade.price,
            total_value=trade.total_value,
            commission=trade.commission,
            executed_at=trade.executed_at,
            message=f"{trade.side} order executed successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error executing trade: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute trade"
        )


@router.get("/trades")
async def get_trade_history(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ticker: Optional[str] = None,
    side: Optional[str] = Query(None, pattern="^(BUY|SELL)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: dict = Depends(get_current_user_mongo)
):
    """Get user's trade history with filtering options"""
    try:
        trade_repo: TradeRepository = get_repository(TradeRepository)
        
        # Build filter
        filter_dict = {"user_id": current_user["_id"]}
        if ticker:
            filter_dict["ticker"] = ticker.upper()
        if side:
            filter_dict["side"] = side
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["$gte"] = start_date
            if end_date:
                date_filter["$lte"] = end_date
            filter_dict["executed_at"] = date_filter
        
        trades = await trade_repo.find_many(filter_dict, limit=limit)
        
        return {
            "trades": trades,
            "count": len(trades),
            "offset": offset,
            "limit": limit
        }
        
    except Exception as e:
        log.error(f"Error fetching trades: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch trade history"
        )


@router.get("/holdings/{ticker}")
async def get_holding_details(
    ticker: str,
    current_user: dict = Depends(get_current_user_mongo)
):
    """Get detailed information about a specific holding"""
    try:
        user_repo: UserRepository = get_repository(UserRepository)
        trade_repo: TradeRepository = get_repository(TradeRepository)
        score_repo: AIScoreRepository = get_repository(AIScoreRepository)
        
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
                detail=f"No holding found for {ticker_upper}"
            )
        
        # Get trade history
        trades = await trade_repo.find_by_ticker(str(current_user["_id"]), ticker_upper)
        
        # Get latest AI score if available
        ai_score = await score_repo.find_latest(str(current_user["_id"]), ticker_upper)
        
        return {
            "holding": holding.model_dump(),
            "trades": trades,
            "trade_count": len(trades),
            "ai_score": ai_score,
            "portfolio_weight": (holding.current_value / portfolio.total_value * 100) if portfolio.total_value > 0 else 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error fetching holding details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch holding details"
        )


@router.post("/deposit")
async def deposit_cash(
    deposit_request: DepositRequest,
    current_user: dict = Depends(get_current_user_mongo)
):
    """Deposit cash into portfolio"""
    try:
        user_repo: UserRepository = get_repository(UserRepository)
        
        portfolio = await user_repo.get_portfolio(str(current_user["_id"]))
        if not portfolio:
            portfolio = Portfolio()
        
        new_balance = portfolio.cash_balance + deposit_request.amount
        success = await user_repo.update_cash_balance(str(current_user["_id"]), new_balance)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update cash balance"
            )
        
        # Log the deposit as a transaction
        log.info(f"User {current_user['_id']} deposited {deposit_request.amount} via {deposit_request.method}")
        
        return {
            "success": True,
            "message": "Cash deposited successfully",
            "amount_deposited": deposit_request.amount,
            "new_balance": new_balance,
            "method": deposit_request.method,
            "timestamp": datetime.now(timezone.utc)
        }
        
    except Exception as e:
        log.error(f"Error processing deposit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process deposit"
        )


@router.post("/withdraw")
async def withdraw_cash(
    amount: float = Query(..., gt=0),
    current_user: dict = Depends(get_current_user_mongo)
):
    """Withdraw cash from portfolio"""
    try:
        user_repo: UserRepository = get_repository(UserRepository)
        
        portfolio = await user_repo.get_portfolio(str(current_user["_id"]))
        if not portfolio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found"
            )
        
        if portfolio.cash_balance < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient cash balance"
            )
        
        new_balance = portfolio.cash_balance - amount
        success = await user_repo.update_cash_balance(str(current_user["_id"]), new_balance)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update cash balance"
            )
        
        return {
            "success": True,
            "message": "Cash withdrawn successfully",
            "amount_withdrawn": amount,
            "new_balance": new_balance,
            "timestamp": datetime.now(timezone.utc)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error processing withdrawal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process withdrawal"
        )


@router.get("/performance")
async def get_performance_metrics(
    period: str = Query("ALL", pattern="^(1D|1W|1M|3M|6M|1Y|ALL)$"),
    current_user: dict = Depends(get_current_user_mongo)
) -> PerformanceMetrics:
    """Get portfolio performance metrics"""
    try:
        user_repo: UserRepository = get_repository(UserRepository)
        trade_repo: TradeRepository = get_repository(TradeRepository)
        
        portfolio = await user_repo.get_portfolio(str(current_user["_id"]))
        if not portfolio or not portfolio.holdings:
            return PerformanceMetrics(
                total_return=0,
                total_return_percent=0,
                best_performer=None,
                worst_performer=None,
                winning_trades=0,
                losing_trades=0,
                win_rate=0,
                avg_win=0,
                avg_loss=0,
                sharpe_ratio=None
            )
        
        # Calculate date range
        end_date = datetime.now(timezone.utc)
        if period == "1D":
            start_date = end_date - timedelta(days=1)
        elif period == "1W":
            start_date = end_date - timedelta(weeks=1)
        elif period == "1M":
            start_date = end_date - timedelta(days=30)
        elif period == "3M":
            start_date = end_date - timedelta(days=90)
        elif period == "6M":
            start_date = end_date - timedelta(days=180)
        elif period == "1Y":
            start_date = end_date - timedelta(days=365)
        else:  # ALL
            start_date = None
        
        # Get trades for the period
        filter_dict = {"user_id": current_user["_id"]}
        if start_date:
            filter_dict["executed_at"] = {"$gte": start_date}
        
        trades = await trade_repo.find_many(filter_dict)
        
        # Calculate metrics
        total_invested = sum(h.quantity * h.avg_cost for h in portfolio.holdings)
        total_current = sum(h.current_value for h in portfolio.holdings)
        total_return = total_current - total_invested
        total_return_percent = (total_return / total_invested * 100) if total_invested > 0 else 0
        
        # Find best and worst performers
        performers = []
        for h in portfolio.holdings:
            performers.append({
                "ticker": h.ticker,
                "pnl_percent": h.pnl_percent,
                "pnl": h.pnl
            })
        
        performers.sort(key=lambda x: x["pnl_percent"], reverse=True)
        best_performer = performers[0] if performers else None
        worst_performer = performers[-1] if performers else None
        
        # Calculate trade statistics
        winning_trades = sum(1 for t in trades if t.get("side") == "SELL" and t.get("pnl", 0) > 0)
        losing_trades = sum(1 for t in trades if t.get("side") == "SELL" and t.get("pnl", 0) < 0)
        total_trades = winning_trades + losing_trades
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Calculate average win/loss (simplified)
        wins = [t.get("pnl", 0) for t in trades if t.get("side") == "SELL" and t.get("pnl", 0) > 0]
        losses = [abs(t.get("pnl", 0)) for t in trades if t.get("side") == "SELL" and t.get("pnl", 0) < 0]
        
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        
        return PerformanceMetrics(
            total_return=total_return,
            total_return_percent=total_return_percent,
            best_performer=best_performer,
            worst_performer=worst_performer,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            sharpe_ratio=None  # TODO: Implement Sharpe ratio calculation
        )
        
    except Exception as e:
        log.error(f"Error calculating performance metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate performance metrics"
        )


@router.delete("/holdings/{ticker}")
async def close_position(
    ticker: str,
    current_user: dict = Depends(get_current_user_mongo)
):
    """Close a position (sell all shares of a ticker)"""
    try:
        user_repo: UserRepository = get_repository(UserRepository)
        trade_repo: TradeRepository = get_repository(TradeRepository)
        market_repo: MarketDataRepository = get_repository(MarketDataRepository)
        
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
                detail=f"No position found for {ticker_upper}"
            )
        
        # Get current market price
        market_data = await market_repo.find_by_ticker(ticker_upper)
        current_price = market_data["current_price"] if market_data else holding.last_price
        
        # Create sell trade for entire position
        trade = Trade(
            user_id=PyObjectId(str(current_user["_id"])),
            ticker=ticker_upper,
            side="SELL",
            quantity=holding.quantity,
            price=current_price,
            commission=holding.quantity * current_price * 0.001
        )
        
        # Execute trade
        trade_id = await trade_repo.execute_trade(trade, user_repo)
        
        if not trade_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to close position"
            )
        
        return {
            "success": True,
            "message": f"Position closed for {ticker_upper}",
            "trade_id": trade_id,
            "quantity_sold": holding.quantity,
            "price": current_price,
            "total_value": trade.total_value,
            "realized_pnl": holding.pnl
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error closing position: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to close position"
        )