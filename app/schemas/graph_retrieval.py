"""Schemas for graph retrieval."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GraphRetrievalRequest(BaseModel):
    query: str
    database_id: Optional[int] = None
    table_id: Optional[int] = None
    related_table_id: Optional[int] = None
    depth: int = Field(default=2, ge=1, le=4)
    max_paths: int = Field(default=5, ge=1, le=10)


class GraphNodeItem(BaseModel):
    table_id: int
    schema_id: int
    schema_name: str
    table_name: str
    table_type: str
    degree: int
    in_degree: int
    out_degree: int
    depth: int
    is_isolated: bool


class GraphPathStepItem(BaseModel):
    source_table_id: int
    target_table_id: int
    source_table_name: str
    target_table_name: str
    relationship_type: str
    join_columns: List[Dict[str, Any]] = Field(default_factory=list)
    relationship_strength: float


class GraphPathItem(BaseModel):
    source_table_id: int
    target_table_id: int
    hops: int
    steps: List[GraphPathStepItem] = Field(default_factory=list)


class GraphRetrievalResponse(BaseModel):
    database_id: Optional[int] = None
    query: str
    latency_ms: float = 0.0
    neighbors: List[GraphNodeItem] = Field(default_factory=list)
    shortest_paths: List[GraphPathItem] = Field(default_factory=list)
    contextual_retrieval: List[GraphNodeItem] = Field(default_factory=list)
    lineage: List[Dict[str, Any]] = Field(default_factory=list)

