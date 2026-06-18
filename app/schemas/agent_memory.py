"""Schemas for agent memory and query history retrieval."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentMemoryCreate(BaseModel):
    database_id: int
    query_text: str
    response_text: Optional[str] = None
    context_json: Dict[str, Any] = Field(default_factory=dict)
    memory_type: str = "query_history"
    tags: List[str] = Field(default_factory=list)
    trace_id: Optional[str] = None


class AgentMemoryResponse(BaseModel):
    id: int
    database_id: int
    query_text: str
    response_text: Optional[str] = None
    context_json: Dict[str, Any] = Field(default_factory=dict)
    memory_type: str
    tags: List[str] = Field(default_factory=list)
    embedding_model: Optional[str] = None
    vector_id: Optional[str] = None
    trace_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class AgentMemorySearchRequest(BaseModel):
    database_id: int
    query: str
    top_k: int = Field(default=5, ge=1, le=20)


class AgentMemorySearchHit(BaseModel):
    score: float
    id: int
    query_text: str
    response_text: Optional[str] = None
    memory_type: str
    tags: List[str] = Field(default_factory=list)
    trace_id: Optional[str] = None
    created_at: Optional[str] = None


class AgentMemoryHistoryResponse(BaseModel):
    database_id: int
    total: int
    results: List[AgentMemoryResponse] = Field(default_factory=list)


class AgentMemorySearchResponse(BaseModel):
    database_id: int
    query: str
    total_hits: int
    results: List[AgentMemorySearchHit] = Field(default_factory=list)


class AgentMemoryHealthResponse(BaseModel):
    database_id: int
    memory_rows: int
    vector_count: int
    search_health: bool
    status: str
