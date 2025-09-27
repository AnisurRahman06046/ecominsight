"""Request and response models."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class QueryRequest(BaseModel):
    """Query request model."""

    shop_id: str = Field(..., description="Shop/tenant identifier")
    question: str = Field(..., description="Natural language question")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    use_cache: bool = Field(True, description="Whether to use cached results")


class QueryResponse(BaseModel):
    """Query response model."""

    shop_id: str
    question: str
    answer: str = Field(..., description="Natural language answer")
    data: Optional[Any] = Field(None, description="Raw query results (can be dict, list, or primitive)")
    query_type: str = Field(..., description="Type of query (kpi/llm/rag)")
    processing_time: float = Field(..., description="Time taken in seconds")
    cached: bool = Field(False, description="Whether result was cached")
    metadata: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: datetime
    services: Dict[str, bool]
    version: str


class KPIDefinition(BaseModel):
    """KPI definition model."""

    name: str
    patterns: List[str] = Field(..., description="Text patterns to match")
    collection: str = Field(..., description="MongoDB collection")
    pipeline_template: str = Field(..., description="Aggregation pipeline template")
    answer_template: str = Field(..., description="Answer format template")
    cache_ttl: Optional[int] = Field(3600, description="Cache time in seconds")


class RAGDocument(BaseModel):
    """Document for RAG system."""

    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)