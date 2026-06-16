"""Schemas for embedding documents."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EmbeddingDocumentItem(BaseModel):
    id: int
    database_id: int
    document_type: str
    source_package: Optional[str] = None
    content: str
    metadata_json: str = Field(default="{}")
    embedding_model: Optional[str] = None
    vector_id: Optional[str] = None
    trace_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EmbeddingDocumentListResponse(BaseModel):
    database_id: int
    documents: list[EmbeddingDocumentItem] = Field(default_factory=list)

