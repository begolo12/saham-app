from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class LearningSummary(BaseModel):
    total_records: int
    pending_evaluation: int
    evaluated: int
    accuracy: float
    by_signal: List[Dict[str, Any]]
    recent: List[Dict[str, Any]]
    rule: str
    updated_at: str


class EvaluationRequest(BaseModel):
    limit: int = 50


class RecommendationHistory(BaseModel):
    symbol: str
    history: List[Dict[str, Any]]
    updated_at: str
