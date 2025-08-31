from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List

# === Users ===
class UserCreate(BaseModel):
    email: str
    name: Optional[str] = None

class UserOut(BaseModel):
    id: str = Field(alias="_id")
    email: str
    name: Optional[str] = None

# === Holdings ===
class HoldingUpsert(BaseModel):
    user_id: str
    ticker: str
    quantity: float
    avg_cost: float

class HoldingOut(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    ticker: str
    quantity: float
    avg_cost: float
    last_price: float | None = None
    market_value: float | None = None
    pnl_abs: float | None = None
    pnl_pct: float | None = None

class PortfolioSummary(BaseModel):
    user_id: str
    total_cost: float
    total_value: float
    total_pnl_abs: float
    total_pnl_pct: float
    positions: List[HoldingOut]
