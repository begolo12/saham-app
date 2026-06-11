from pydantic import BaseModel
from typing import Optional, Dict, Any


class MarketSummary(BaseModel):
    name: str
    symbol: str
    price: Optional[float] = None
    change: float = 0
    change_percent: float = 0
    high_52w: Optional[float] = None
    low_52w: Optional[float] = None
    volume: int = 0
    updated_at: str


class MarketRegime(BaseModel):
    regime: str
    confidence: float
    ihsg_trend: Optional[float] = None
    volatility: Optional[float] = None
