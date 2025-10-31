# backend/app/db/schemas.py
"""MongoDB document schemas using Pydantic for validation"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId
from typing import Any
from bson import ObjectId
from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic_core import core_schema
class PyObjectId(ObjectId):
    """MongoDB ObjectId type with Pydantic v2 support."""
    @classmethod
    def __get_pydantic_core_schema__(cls, _source: Any, handler: GetCoreSchemaHandler):
        def validate(v: Any) -> ObjectId:
            if isinstance(v, ObjectId):
                return v
            if isinstance(v, str) and ObjectId.is_valid(v):
                return ObjectId(v)
            raise ValueError("Invalid ObjectId")
        return core_schema.no_info_after_validator_function(
            validate,
            core_schema.union_schema([
                core_schema.is_instance_schema(ObjectId),
                core_schema.str_schema(),
            ])
        )

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema_, handler: GetJsonSchemaHandler):
        js = handler(core_schema_)
        js.update(type="string", examples=["64f1a2b3c4d5e67890ab12cd"])
        return js
class MongoBaseModel(BaseModel):
    """Base model for MongoDB documents"""
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class User(MongoBaseModel):
    """User document schema"""
    email: str = Field(..., index=True, unique=True)
    username: str = Field(..., index=True)
    hashed_password: str
    is_active: bool = True
    is_verified: bool = False
    
    # Portfolio embedded
    portfolio: Portfolio = Field(default_factory=lambda: Portfolio())


class Portfolio(BaseModel):
    """Embedded portfolio schema"""
    cash_balance: float = Field(default=0.0, ge=0)
    holdings: List[Holding] = Field(default_factory=list)
    total_value: float = Field(default=0.0, ge=0)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Holding(BaseModel):
    """Embedded holding schema"""
    ticker: str = Field(..., max_length=16)
    quantity: float = Field(..., gt=0)
    avg_cost: float = Field(..., gt=0)
    last_price: float = Field(default=0.0, ge=0)
    current_value: float = Field(default=0.0, ge=0)
    pnl: float = Field(default=0.0)  # Profit/Loss
    pnl_percent: float = Field(default=0.0)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Trade(MongoBaseModel):
    """Trade document schema"""
    user_id: PyObjectId = Field(..., index=True)
    ticker: str = Field(..., max_length=16, index=True)
    side: str = Field(..., pattern="^(BUY|SELL)$")
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    total_value: float = Field(default=0.0)
    commission: float = Field(default=0.0, ge=0)
    
    # Status tracking
    status: str = Field(default="EXECUTED", pattern="^(PENDING|EXECUTED|CANCELLED)$")
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def calculate_total(self) -> float:
        """Calculate total value including commission"""
        base_value = self.quantity * self.price
        if self.side == "BUY":
            return base_value + self.commission
        else:  # SELL
            return base_value - self.commission


class AIScore(MongoBaseModel):
    """AI Score document schema"""
    # Add model_config to disable protected namespace check for this model
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        protected_namespaces=()  # This disables the model_ namespace protection
    )
    
    user_id: PyObjectId = Field(..., index=True)
    ticker: str = Field(..., max_length=16, index=True)
    
    # Scores
    technical_score: float = Field(..., ge=0, le=100)
    fundamental_score: float = Field(..., ge=0, le=100)
    sentiment_score: float = Field(..., ge=0, le=100)
    overall_score: float = Field(..., ge=0, le=100)
    
    # Analysis details
    analysis: dict = Field(default_factory=dict)
    confidence: float = Field(..., ge=0, le=1)
    
    # Metadata
    model_version: str = Field(default="v1.0")
    expires_at: datetime  # When this score should be refreshed


class Recommendation(MongoBaseModel):
    """AI Recommendation document schema"""
    user_id: PyObjectId = Field(..., index=True)
    ticker: str = Field(..., max_length=16, index=True)
    
    # Recommendation
    action: str = Field(..., pattern="^(STRONG_BUY|BUY|HOLD|SELL|STRONG_SELL)$")
    confidence: float = Field(..., ge=0, le=1)
    target_price: Optional[float] = Field(None, gt=0)
    stop_loss: Optional[float] = Field(None, gt=0)
    
    # Position sizing
    suggested_allocation: float = Field(..., ge=0, le=1)  # Percentage of portfolio
    suggested_quantity: Optional[int] = Field(None, gt=0)
    
    # Reasoning
    reasoning: str
    risk_factors: List[str] = Field(default_factory=list)
    opportunity_factors: List[str] = Field(default_factory=list)
    
    # Validity
    valid_until: datetime
    is_active: bool = True


class MarketData(MongoBaseModel):
    """Market data cache schema"""
    ticker: str = Field(..., max_length=16, index=True, unique=True)
    
    # Price data
    current_price: float = Field(..., gt=0)
    open_price: float = Field(..., gt=0)
    high: float = Field(..., gt=0)
    low: float = Field(..., gt=0)
    close: float = Field(..., gt=0)
    volume: int = Field(..., ge=0)
    
    # Change metrics
    change: float = Field(default=0.0)
    change_percent: float = Field(default=0.0)
    
    # Additional data
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    
    # Metadata
    source: str = Field(default="yahoo_finance")
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))