from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class PositionCreate(BaseModel):
    symbol: str
    qty: float
    avg_price: float
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    notes: Optional[str] = None


class PositionResponse(BaseModel):
    id: int
    symbol: str
    qty: float
    avg_price: float
    current_price: float
    market_value: float
    cost: float
    pnl: float
    pnl_pct: float
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    notes: Optional[str] = None


class PortfolioSummary(BaseModel):
    positions: List[Dict[str, Any]]
    summary: Dict[str, Any]
    updated_at: str
