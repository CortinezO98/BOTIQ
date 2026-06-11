"""
Schemas para el dashboard de métricas de BOTIQ.
"""

from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class FrequentQuery(BaseModel):
    query: str
    count: int
    module: str
    last_seen: datetime


class ServerMetric(BaseModel):
    server_name: str
    downtime_count: int
    avg_memory: Optional[float]
    avg_cpu: Optional[float]
    last_incident: Optional[datetime]


class SupportGap(BaseModel):
    """
    Falencias detectadas: preguntas que el RAG no pudo responder bien.
    """
    query: str
    frequency: int
    avg_confidence: float
    suggested_action: str


class DashboardMetrics(BaseModel):
    total_conversations: int
    total_messages: int
    avg_response_time_ms: float
    total_tokens_used: float
    escalations_to_aranda: int
    most_frequent_queries: List[FrequentQuery]
    server_metrics: List[ServerMetric]
    support_gaps: List[SupportGap]
    period_start: datetime
    period_end: datetime


class MetricsSummary(BaseModel):
    today_conversations: int
    week_conversations: int
    top_module: str
    most_reported_server: Optional[str]
    support_gap_count: int
