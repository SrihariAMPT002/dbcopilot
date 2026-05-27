from future import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# Base Semantic Schema


class SchemaSemanticBase(BaseModel):
    source_type: str = Field(..., examples=["sql", "nosql"])

    entity_type: str = Field(
        ...,
        examples=["table", "collection"],
    )

    entity_name: str

# Create Semantic Record


class SchemaSemanticCreate(SchemaSemanticBase):
    database_id: UUID

    schema_id: Optional[UUID] = None

    table_id: Optional[UUID] = None

    collection_id: Optional[UUID] = None

    business_summary: Optional[str] = None

    likely_usage: Optional[List[str]] = None

    important_fields: Optional[List[str]] = None

    possible_questions: Optional[List[str]] = None

    semantic_keywords: Optional[List[str]] = None

    generated_prompt: Optional[str] = None

    enrichment_status: str = "pending"

# Update Semantic Record


class SchemaSemanticUpdate(BaseModel):
    business_summary: Optional[str] = None

    likely_usage: Optional[List[str]] = None

    important_fields: Optional[List[str]] = None

    possible_questions: Optional[List[str]] = None

    semantic_keywords: Optional[List[str]] = None

    generated_prompt: Optional[str] = None

    enrichment_status: Optional[str] = None

# Semantic Response


class SchemaSemanticResponse(SchemaSemanticBase):
    id: UUID

    database_id: UUID

    schema_id: Optional[UUID] = None

    table_id: Optional[UUID] = None

    collection_id: Optional[UUID] = None

    business_summary: Optional[str] = None

    likely_usage: Optional[List[str]] = None

    important_fields: Optional[List[str]] = None

    possible_questions: Optional[List[str]] = None

    semantic_keywords: Optional[List[str]] = None

    generated_prompt: Optional[str] = None

    enrichment_status: str

    generated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )

# Semantic Generation Request


class SemanticGenerationRequest(BaseModel):
    regenerate_existing: bool = False


# Semantic Generation Response


class SemanticGenerationResponse(BaseModel):
    success: bool

    database_id: UUID

    processed_entities: int

    failed_entities: int

    message: str

# Semantic Summary Card

class SemanticSummaryCard(BaseModel):
    entity_name: str

    entity_type: str

    business_summary: Optional[str] = None

    likely_usage: Optional[List[str]] = None

    possible_questions: Optional[List[str]] = None

    enrichment_status: str

    # AI Readiness Status

class AIReadinessStatus(BaseModel):
    entity_name: str

    semantic_ready: bool

    embeddings_ready: bool

    prompt_ready: bool

    metadata_quality_score: float