from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class HoldingIn(BaseModel):
    ticker: str
    quantity: float = Field(..., gt=0)
    avg_cost: float = Field(..., gt=0)

class HoldingOut(BaseModel):
    ticker: str
    quantity: float
    avg_cost: float
    last_price: float
    market_value: float
    pnl_abs: float
    pnl_pct: float

class TradeIn(BaseModel):
    ticker: str
    side: str  # BUY or SELL
    qty: float = Field(..., gt=0)
    price: Optional[float] = None  # if not provided, we’ll fetch quote

class TradeOut(BaseModel):
    ticker: str
    side: str
    qty: float
    price: float

class MetricsOut(BaseModel):
    total_value: float
    total_cost: float
    pnl_abs: float
    pnl_pct: float
    weights: Dict[str, float]
    asset_volatility: Dict[str, float]
    portfolio_volatility: float

class RebalanceRequest(BaseModel):
    max_weight: float = 0.4
    target_vol: float = 0.25
    cash_buffer_pct: float = 0.0 # keep this much as cash (0-0.2 typical)
    top_n_news: int = 5

class RebalanceAction(BaseModel):
    ticker: str
    current_weight: float
    suggested_weight: float
    delta_weight: float
    sentiment: str
    momentum_30d: float

class RebalancePlan(BaseModel):
    suggested_weights: Dict[str, float]
    actions: List[RebalanceAction]
