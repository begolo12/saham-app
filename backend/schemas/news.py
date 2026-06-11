from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class NewsItem(BaseModel):
    title: str
    summary: str
    url: str
    published_at: str
    sentiment: str = 'NEUTRAL'
    sentiment_score: int = 0


class SentimentResponse(BaseModel):
    symbol: str
    sentiment: str
    sentiment_score: int
    positive_count: int
    negative_count: int
    neutral_count: int
    reason: str
    items: List[Dict[str, Any]]
    updated_at: str


class NewsResponse(BaseModel):
    items: List[Any]
    updated_at: str
