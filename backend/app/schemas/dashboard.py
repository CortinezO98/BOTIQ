from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class DashboardMetrics(BaseModel):
    total_conversations: int
    total_messages: int
    avg_response_time_ms: float
    total_tokens_used: float
    escalations_to_aranda: int
    open_knowledge_gaps: int
    period_start: datetime
    period_end: datetime

class MetricsSummary(BaseModel):
    today_conversations: int
    week_conversations: int
    top_module: str
    support_gap_count: int
    most_reported_server: Optional[str] = None

class ConvByModule(BaseModel):
    module: str
    count: int

class ConvByDay(BaseModel):
    date: str
    count: int

class TopFAQ(BaseModel):
    question: str
    hits: int
    category: str

class TokenConsumption(BaseModel):
    date: str
    tokens: int

class KnowledgeGapItem(BaseModel):
    id: str
    query: str
    module: str
    frequency: int
    avg_confidence: float
    last_seen: datetime
    status: str

class EscalationRate(BaseModel):
    total: int
    escalated: int
    rate_pct: float
