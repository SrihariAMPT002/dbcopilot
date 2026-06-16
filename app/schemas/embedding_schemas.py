"""
Pydantic DTOs for embedding generation and semantic search endpoints.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EmbeddingGenerateResponse(BaseModel):
    database_id: int
    database_name: str
    embedding_model: str
    tables_indexed: int
    vectors_indexed: int
    token_usage: Dict[str, int] = Field(default_factory=dict)
    latency_ms: float
    success: bool
    message: str


class EmbeddingRefreshRequest(BaseModel):
    table_id: Optional[int] = None


class CollectionStatus(BaseModel):
    collection_name: str
    vectors: int
    indexed_tables: int
    last_indexed_at: Optional[datetime] = None


class EmbeddingStatusResponse(BaseModel):
    database_id: int
    database_name: str
    embedding_model: str
    embedding_health: bool
    qdrant_health: bool
    total_tables: int
    indexed_tables: int
    completed_tables: int
    failed_tables: int
    vectors_total: int
    vector_counts: Dict[str, int]
    collections: List[CollectionStatus]
    last_generated_at: Optional[datetime] = None
    status_breakdown: Dict[str, int]
    message: str

    model_config = {"from_attributes": True}


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="Natural language search query")
    db_id: Optional[int] = Field(default=None, description="Restrict results to this database")
    top_k: int = Field(default=5, ge=1, le=20, description="Maximum results to return")
    collection: str = Field(
        default="schema_tables",
        description="schema_tables | schema_relationships | schema_prompts | all",
    )


class SemanticSearchHit(BaseModel):
    score: float
    database_id: int
    database_name: str
    schema_name: str
    table_name: str
    table_type: str
    text: str
    semantic_summary: Optional[str] = None
    column_names: List[str] = Field(default_factory=list)
    relationships: List[str] = Field(default_factory=list)
    collection_name: str
    extra: Dict[str, Any] = Field(default_factory=dict)


class SemanticSearchResponse(BaseModel):
    query: str
    collection: str
    db_id: Optional[int]
    total_results: int
    results: List[SemanticSearchHit]
