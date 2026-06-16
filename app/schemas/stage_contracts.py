"""Explicit stage contracts for the DB Copilot execution pipeline.

These contracts are the canonical target shapes for the AI intelligence platform.
They are intentionally lightweight and are meant to describe, not execute, the
pipeline.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StageStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    fallback = "fallback"
    retrying = "retrying"


class RetryMetadata(BaseModel):
    attempt: int = 0
    max_attempts: int = 1
    retry_after_seconds: int = 0
    last_error: Optional[str] = None
    is_retriable: bool = True


class ExecutionMetadata(BaseModel):
    stage_name: str
    status: StageStatus = StageStatus.pending
    execution_status: str = "pending"
    fallback_used: bool = False
    retry_count: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    trace_id: Optional[str] = None
    trace_url: Optional[str] = None
    prompt_id: Optional[str] = None
    prompt_version: Optional[str] = None
    model_name: Optional[str] = None
    metadata_fingerprint: Optional[str] = None
    observability: Dict[str, Any] = Field(default_factory=dict)
    retry: RetryMetadata = Field(default_factory=RetryMetadata)


class MetadataStageInput(BaseModel):
    database_id: int
    connection_id: Optional[int] = None
    source_type: Optional[str] = None


class MetadataStageOutput(BaseModel):
    database_id: int
    schema_count: int = 0
    table_count: int = 0
    column_count: int = 0
    relationship_count: int = 0
    metadata_fingerprint: Optional[str] = None


class GovernanceStageInput(BaseModel):
    database_id: int
    table_id: Optional[int] = None
    table_name: Optional[str] = None
    columns: List[Dict[str, Any]] = Field(default_factory=list)
    rulebook_version: Optional[str] = None


class GovernanceStageOutput(BaseModel):
    database_id: int
    table_id: Optional[int] = None
    table_name: Optional[str] = None
    table_summary: Optional[str] = None
    business_purpose: Optional[str] = None
    is_pii: bool = False
    pii_type: Optional[str] = None
    risk_level: Optional[str] = None
    confidence_score: float = 0.0
    classification_source: Optional[str] = None
    resolved_columns: List[Dict[str, Any]] = Field(default_factory=list)


class SemanticsStageInput(BaseModel):
    database_id: int
    metadata_summary: Dict[str, Any] = Field(default_factory=dict)


class SemanticsStageOutput(BaseModel):
    database_id: int
    business_domain: Optional[str] = None
    business_summary: Optional[str] = None
    key_entities: List[str] = Field(default_factory=list)
    business_glossary: List[Dict[str, Any]] = Field(default_factory=list)
    suggested_use_cases: List[str] = Field(default_factory=list)
    confidence_score: float = 0.0


class RelationshipsStageInput(BaseModel):
    database_id: int
    cluster_id: Optional[str] = None
    table_ids: List[int] = Field(default_factory=list)
    tables: List[Dict[str, Any]] = Field(default_factory=list)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    semantics: Dict[str, Any] = Field(default_factory=dict)


class RelationshipsStageOutput(BaseModel):
    database_id: int
    cluster_id: Optional[str] = None
    cluster_label: Optional[str] = None
    cluster_summary: Optional[str] = None
    cluster_confidence: float = 0.0
    entity_graph: List[Dict[str, Any]] = Field(default_factory=list)
    hidden_relationships: List[Dict[str, Any]] = Field(default_factory=list)
    lifecycle_flows: List[Dict[str, Any]] = Field(default_factory=list)


class KPIStageInput(BaseModel):
    database_id: int
    domain: Optional[str] = None
    semantics: Dict[str, Any] = Field(default_factory=dict)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    governance: List[Dict[str, Any]] = Field(default_factory=list)


class KPIStageOutput(BaseModel):
    database_id: int
    kpi_count: int = 0
    catalog: List[Dict[str, Any]] = Field(default_factory=list)
    definitions: List[Dict[str, Any]] = Field(default_factory=list)
    lineage: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_score: float = 0.0


class PromptStageInput(BaseModel):
    database_id: int
    registry_context: Dict[str, Any] = Field(default_factory=dict)
    package_context: Dict[str, Any] = Field(default_factory=dict)


class PromptStageOutput(BaseModel):
    database_id: int
    prompt_count: int = 0
    prompt_inventory: List[Dict[str, Any]] = Field(default_factory=list)
    artifact_count: int = 0


class ReadinessStageInput(BaseModel):
    database_id: int
    snapshot_id: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    governance: Dict[str, Any] = Field(default_factory=dict)
    semantics: Dict[str, Any] = Field(default_factory=dict)
    relationships: Dict[str, Any] = Field(default_factory=dict)
    kpi: Dict[str, Any] = Field(default_factory=dict)
    prompts: Dict[str, Any] = Field(default_factory=dict)


class ReadinessStageOutput(BaseModel):
    database_id: int
    readiness_status: Optional[str] = None
    overall_score: int = 0
    category_scores: Dict[str, int] = Field(default_factory=dict)
    ai_summary: Optional[str] = None
    ai_recommendations: List[str] = Field(default_factory=list)
    ai_risks: List[str] = Field(default_factory=list)
    ai_roadmap: List[str] = Field(default_factory=list)
    ai_confidence: float = 0.0


class StageContract(BaseModel):
    stage_name: str
    input_schema: str
    output_schema: str
    status: StageStatus = StageStatus.pending
    retry_metadata: RetryMetadata = Field(default_factory=RetryMetadata)
    execution_metadata: ExecutionMetadata = Field(
        default_factory=lambda: ExecutionMetadata(stage_name="")
    )


class StageDependency(BaseModel):
    stage: str
    depends_on: list[str] = Field(default_factory=list)


class StageNodeStatus(BaseModel):
    stage: str
    status: str = "pending"
    retries: int = 0
    job_id: Optional[int] = None
    depends_on: list[str] = Field(default_factory=list)


class StageGraphResponse(BaseModel):
    database_id: int
    stages: list[StageNodeStatus] = Field(default_factory=list)
    graph: list[StageDependency] = Field(default_factory=list)
    resumable: bool = True
    message: str = "Stage graph loaded."


class StageProgressItem(BaseModel):
    stage: str
    job_id: Optional[int] = None
    status: str = "pending"
    progress_percentage: int = 0
    retries: int = 0
    failure_reason: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    depends_on: list[str] = Field(default_factory=list)


class StageProgressResponse(BaseModel):
    database_id: int
    parent_job_id: Optional[int] = None
    overall_status: str = "pending"
    overall_progress_percentage: int = 0
    current_stage: Optional[str] = None
    completed_stages: int = 0
    running_stages: int = 0
    failed_stages: int = 0
    pending_stages: int = 0
    stages: list[StageProgressItem] = Field(default_factory=list)
    graph: list[StageDependency] = Field(default_factory=list)
    message: str = "Stage progress loaded."


STAGE_CONTRACTS: dict[str, StageContract] = {
    "metadata": StageContract(
        stage_name="metadata",
        input_schema="MetadataStageInput",
        output_schema="MetadataStageOutput",
    ),
    "governance": StageContract(
        stage_name="governance",
        input_schema="GovernanceStageInput",
        output_schema="GovernanceStageOutput",
    ),
    "semantics": StageContract(
        stage_name="semantics",
        input_schema="SemanticsStageInput",
        output_schema="SemanticsStageOutput",
    ),
    "relationships": StageContract(
        stage_name="relationships",
        input_schema="RelationshipsStageInput",
        output_schema="RelationshipsStageOutput",
    ),
    "kpi": StageContract(
        stage_name="kpi",
        input_schema="KPIStageInput",
        output_schema="KPIStageOutput",
    ),
    "prompt": StageContract(
        stage_name="prompt",
        input_schema="PromptStageInput",
        output_schema="PromptStageOutput",
    ),
    "readiness": StageContract(
        stage_name="readiness",
        input_schema="ReadinessStageInput",
        output_schema="ReadinessStageOutput",
    ),
}
