from pydantic import BaseModel
from typing import Optional, Dict, Any, List


class TradePlan(BaseModel):
    action: str
    entry_price: float
    target_price: float
    stop_loss: float
    horizon_days: int
    check_every: str
    take_profit_pct: float
    stop_loss_pct: float
    instruction: str
    confidence: str


class StockCard(BaseModel):
    symbol: str
    name: str
    price: Optional[float] = None
    change_percent: float = 0
    signal: str = 'NEUTRAL'
    signal_strength: int = 50
    sector: str = 'Lainnya'
    volume: int = 0
    avg_volume: int = 0
    potential_score: float = 0
    trend_5d: float = 0
    trend_20d: float = 0
    rsi14: float = 50
    volume_ratio: float = 1
    trade_plan: Optional[Dict[str, Any]] = None


class TechnicalDetail(BaseModel):
    rsi: Optional[float] = None
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    bollinger_upper: Optional[float] = None
    bollinger_middle: Optional[float] = None
    bollinger_lower: Optional[float] = None
    signal: str = 'NEUTRAL'
    strength: int = 50
    reasons: List[str] = []


class FundamentalDetail(BaseModel):
    pe_ratio: Optional[float] = None
    pbv: Optional[float] = None
    dividend_yield: Optional[float] = None
    eps: Optional[float] = None
    market_cap: Optional[float] = None
    high_52w: Optional[float] = None
    low_52w: Optional[float] = None
    signal: str = 'NEUTRAL'
    strength: int = 50
    reasons: List[str] = []


class StockDetail(BaseModel):
    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    sector: str
    industry: Optional[str] = None
    market_cap: Optional[Any] = None
    technical: Dict[str, Any]
    fundamental: Dict[str, Any]
    overall_signal: str
    overall_label: str
    overall_strength: int
    overall_reasons: List[str]
    decision_summary: str
    key_drivers: List[str]
    risk_notes: List[str]
    trade_plan: Dict[str, Any]
    daily_check: Dict[str, Any]
    news_sentiment: Optional[Dict[str, Any]] = None
    volatility_pct: Optional[float] = None
    updated_at: str


class StockHistory(BaseModel):
    symbol: str
    period: str
    dates: List[str]
    open: List[float]
    high: List[float]
    low: List[float]
    close: List[float]
    volume: List[int]
    updated_at: str


class StockSearchResult(BaseModel):
    stocks: List[Dict[str, Any]]
    query: str
    count: Optional[int] = None
    updated_at: str


class SignalResponse(BaseModel):
    symbol: str
    overall_signal: str
    overall_strength: int
    technical: Dict[str, Any]
    fundamental: Dict[str, Any]
    updated_at: str


class BatchStockRequest(BaseModel):
    symbols: Optional[str] = None
