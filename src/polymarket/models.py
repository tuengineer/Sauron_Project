# src/polymarket/models.py
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime
from typing import List, Optional, Literal

class Market(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    tags: List[str] = []
    yes_price: Decimal = Field(..., ge=0, le=1)
    no_price: Decimal = Field(..., ge=0, le=1)
    volume: Decimal = Field(default=Decimal("0"))
    liquidity: Decimal = Field(default=Decimal("0"))
    resolution_date: datetime
    status: Literal["active", "resolved", "closed"] = "active"

class OrderBookLevel(BaseModel):
    price: Decimal
    size: Decimal

class OrderBook(BaseModel):
    market_id: str
    bids: List[OrderBookLevel]  # mayor a menor
    asks: List[OrderBookLevel]  # menor a mayor
    timestamp_ms: Optional[int] = None

class Order(BaseModel):
    market_id: str
    side: Literal["YES", "NO"]
    size: Decimal = Field(..., gt=0)
    price: Decimal = Field(..., gt=0, le=1)
    # Post-ejecución
    filled_size: Optional[Decimal] = None
    remaining_size: Optional[Decimal] = None
    executed_price: Optional[Decimal] = None
    slippage: Optional[Decimal] = None
    status: Literal["pending", "filled", "partial", "cancelled", "rejected"] = "pending"
    latency_ms: Optional[float] = None
