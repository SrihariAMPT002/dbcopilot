"""
Pydantic v2 schemas for FastAPI request/response validation.

Convention:
  *Request  — incoming data from client
  *Response — outgoing data to client (never leaks credentials)
  *Summary  — lightweight read model for lists
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.metadata import ConnectionStatus, DatabaseType, SyncStatus, TableType


# ── Shared base ───────────────────────────────────────────────────────────────

class APIResponse(BaseModel):
    """Generic wrapper for all API responses."""
    success: bool
    message: str
    data: Optional[Any] = None


# ── Connection ────────────────────────────────────────────────────────────────

class ConnectionRequest(BaseModel):
    """Credentials supplied by the user to connect a new database."""
    name: str = Field(..., min_length=1, max_length=255, description="Human-readable name for this connection")
    db_type: DatabaseType = Field(..., description="Database engine type")
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(..., ge=1, le=65535)
    database_name: str = Field(..., min_length=1, max_length=255)
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1)
    ssl_enabled: bool = Field(default=False, description="Enable SSL/TLS for the database connection")

    @field_validator("host")
    @classmethod
    def strip_host(cls, v: str) -> str:
        return v.strip()

    @field_validator("db_type", mode="before")
    @classmethod
    def normalise_db_type(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.lower()
        return v

    model_config = {"use_enum_values": True}


class TestConnectionRequest(ConnectionRequest):
    """Identical to ConnectionRequest — kept separate for semantic clarity."""
    pass


class TestConnectionResponse(BaseModel):
    success: bool
    message: str
    latency_ms: Optional[float] = None
    server_version: Optional[str] = None
    databases_accessible: Optional[int] = None


class ConnectionSummary(BaseModel):
    """Lightweight read model used in list endpoints."""
    id: int
    name: str
    db_type: str
    host: str
    port: int
    database_name: str
    username: str
    ssl_enabled: bool = False
    status: str
    last_sync_at: Optional[datetime]
    created_at: datetime
    schema_count: int = 0
    table_count: int = 0
    last_error: Optional[str] = None

    model_config = {"from_attributes": True}


class ConnectionDetail(ConnectionSummary):
    """Full connection detail including schemas."""
    schemas: List["SchemaResponse"] = []

    model_config = {"from_attributes": True}


# ── Schema ────────────────────────────────────────────────────────────────────

class SchemaResponse(BaseModel):
    id: int
    connected_db_id: int
    name: str
    description: Optional[str]
    created_at: datetime
    table_count: int = 0

    model_config = {"from_attributes": True}


class SchemaDetail(SchemaResponse):
    tables: List["TableResponse"] = []

    model_config = {"from_attributes": True}


# ── Table ─────────────────────────────────────────────────────────────────────

class TableResponse(BaseModel):
    id: int
    schema_id: int
    name: str
    table_type: str
    row_count: Optional[int]
    description: Optional[str]
    created_at: datetime
    column_count: int = 0

    model_config = {"from_attributes": True}


class TableDetail(TableResponse):
    columns: List["ColumnResponse"] = []
    relationships: List["RelationshipResponse"] = []

    model_config = {"from_attributes": True}


# ── Column ────────────────────────────────────────────────────────────────────

class ColumnResponse(BaseModel):
    id: int
    table_id: int
    name: str
    data_type: str
    ordinal_position: Optional[int]
    is_nullable: bool
    is_primary_key: bool
    is_foreign_key: bool
    is_unique: bool
    is_indexed: bool
    default_value: Optional[str]
    max_length: Optional[int]
    description: Optional[str]

    model_config = {"from_attributes": True}


# ── Relationship ──────────────────────────────────────────────────────────────

class ColumnSemanticResponse(BaseModel):
    column_id: int
    database_id: int
    business_name: Optional[str] = None
    business_description: Optional[str] = None
    business_meaning: Optional[str] = None
    governance_reasoning: Optional[str] = None
    table_purpose: Optional[str] = None
    prompt_id: Optional[str] = None
    prompt_version: Optional[str] = None
    model_name: Optional[str] = None
    column_category: Optional[str] = None
    table_category: Optional[str] = None
    classification_source: Optional[str] = None
    is_pii: bool = False
    pii_type: Optional[str] = None
    risk_level: Optional[str] = None
    confidence_score: float = 0.0
    generated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    schema_name: Optional[str] = None
    table_name: Optional[str] = None
    column_name: Optional[str] = None

    model_config = {"from_attributes": True}


class GovernancePackageColumnResponse(BaseModel):
    column_name: str
    is_pii: bool = False
    pii_type: Optional[str] = None
    risk_level: Optional[str] = None
    confidence_score: float = 0.0
    business_meaning: Optional[str] = None
    governance_reasoning: Optional[str] = None
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    rule_matches: List[Dict[str, Any]] = Field(default_factory=list)
    sample_patterns: List[str] = Field(default_factory=list)


class GovernancePackageResponse(BaseModel):
    id: int
    database_id: int
    table_id: int
    table_name: str
    schema_name: str
    table_summary: Optional[str] = None
    business_purpose: Optional[str] = None
    pii_columns: List[GovernancePackageColumnResponse] = Field(default_factory=list)
    risk_columns: List[GovernancePackageColumnResponse] = Field(default_factory=list)
    sensitive_columns: List[GovernancePackageColumnResponse] = Field(default_factory=list)
    overall_risk: Optional[str] = None
    confidence_score: float = 0.0
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    rule_matches: List[Dict[str, Any]] = Field(default_factory=list)
    sample_patterns: List[Dict[str, Any]] = Field(default_factory=list)
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    finish_reason: Optional[str] = None
    latency_ms: Optional[float] = None
    prompt_id: Optional[str] = None
    prompt_version: Optional[str] = None
    model_name: Optional[str] = None
    trace_id: Optional[str] = None
    raw_failure_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class GovernancePiiSummaryResponse(BaseModel):
    database_id: int
    table_count: int = 0
    pii_columns: int = 0
    risk_columns: int = 0
    sensitive_columns: int = 0
    governance_packages: int = 0


class GovernanceEvidenceItemResponse(BaseModel):
    id: int
    governance_package_id: int
    column_id: Optional[int] = None
    evidence_type: str
    evidence_source: str
    evidence_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class GovernanceEvidenceResponse(BaseModel):
    database_id: int
    table_id: int
    table_name: Optional[str] = None
    schema_name: Optional[str] = None
    confidence_score: float = 0.0
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    finish_reason: Optional[str] = None
    latency_ms: Optional[float] = None
    evidence: List[GovernanceEvidenceItemResponse] = Field(default_factory=list)


class RelationshipResponse(BaseModel):
    id: int
    table_id: int
    column_name: str
    referenced_table_name: str
    referenced_column_name: str
    referenced_schema: Optional[str]
    constraint_name: Optional[str]

    model_config = {"from_attributes": True}


# ── Sync ──────────────────────────────────────────────────────────────────────

class SyncRequest(BaseModel):
    db_id: int


class SyncLogResponse(BaseModel):
    id: int
    connected_db_id: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    schemas_synced: int
    tables_synced: int
    columns_synced: int
    relationships_synced: int
    error_message: Optional[str]

    model_config = {"from_attributes": True}


class SyncResponse(BaseModel):
    success: bool
    message: str
    sync_log: Optional[SyncLogResponse] = None
    schemas_discovered: int = 0
    tables_discovered: int = 0
    columns_discovered: int = 0


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    db_healthy: bool
    timestamp: datetime


# ── Future AI placeholders ────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Placeholder — will be expanded in the AI layer."""
    db_id: int
    message: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Placeholder response."""
    message: str = "AI querying coming soon. Schema context is ready."
    conversation_id: Optional[str] = None
    sql_generated: Optional[str] = None
    results: Optional[List[Dict]] = None


class GenerateSQLRequest(BaseModel):
    """Placeholder — text-to-SQL."""
    db_id: int
    natural_language_query: str
    schema_context: Optional[str] = None


class GenerateSQLResponse(BaseModel):
    sql: Optional[str] = None
    explanation: Optional[str] = None
    message: str = "Text-to-SQL coming soon."


# ── Phase 2: Embeddings + Retrieval ───────────────────────────────────────────

class EmbeddingCollectionStatus(BaseModel):
    collection_name: str
    vectors: int
    indexed_tables: int = 0
    last_indexed_at: Optional[datetime] = None


class EmbeddingStatusResponse(BaseModel):
    database_id: int
    database_name: str
    embedding_model: str
    embedding_health: bool
    qdrant_health: bool
    indexed_tables: int
    completed_tables: int
    failed_tables: int
    vectors_total: int
    vector_counts: Dict[str, int] = Field(default_factory=dict)
    collections: List[EmbeddingCollectionStatus] = Field(default_factory=list)
    last_generated_at: Optional[datetime] = None
    message: str = "Schema embeddings indexed."


class EmbeddingGenerationResponse(BaseModel):
    success: bool
    message: str
    database_id: int
    tables_indexed: int = 0
    vectors_indexed: int = 0
    embedding_model: str
    latency_ms: float = 0.0
    token_usage: Dict[str, int] = Field(default_factory=dict)


class SemanticSearchRequest(BaseModel):
    db_id: int
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=25)


class SemanticSearchHit(BaseModel):
    score: float
    collection: str
    database_id: int
    table_id: int
    schema_id: int
    schema_name: str
    table_name: str
    table_type: Optional[str] = None
    matched_text: str
    columns: List[str] = Field(default_factory=list)
    relationships: List[str] = Field(default_factory=list)
    prompt_context: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SemanticSearchResponse(BaseModel):
    query: str
    database_id: int
    latency_ms: float = 0.0
    token_usage: Dict[str, int] = Field(default_factory=dict)
    tables: List[SemanticSearchHit] = Field(default_factory=list)
    relationships: List[SemanticSearchHit] = Field(default_factory=list)
    prompt_contexts: List[SemanticSearchHit] = Field(default_factory=list)
    total_hits: int = 0


# ── Phase 3: Relationship Graph ───────────────────────────────────────────────

class JoinColumnResponse(BaseModel):
    source_column: str
    target_column: str


class GraphNodeResponse(BaseModel):
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


class GraphEdgeResponse(BaseModel):
    source_table_id: int
    target_table_id: int
    source_table_name: str
    target_table_name: str
    source_schema_name: str
    target_schema_name: str
    relationship_type: str
    join_columns: List[JoinColumnResponse] = Field(default_factory=list)
    relationship_strength: float
    path_depth: int
    is_circular: bool
    ai_summary: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_model_name: Optional[str] = None
    ai_prompt_id: Optional[str] = None
    ai_prompt_version: Optional[str] = None
    cluster_id: Optional[str] = None
    cluster_size: Optional[int] = None
    estimated_tokens: Optional[int] = None
    actual_input_tokens: Optional[int] = None
    actual_output_tokens: Optional[int] = None
    cluster_summary: Optional[str] = None
    cluster_confidence: Optional[float] = None
    execution_status: Optional[str] = None
    used_fallback: bool = False
    retry_count: int = 0


class GraphMetricsResponse(BaseModel):
    table_count: int
    edge_count: int
    relationship_density: float
    graph_depth: int
    relationship_complexity: float = 0.0
    central_tables: List[str] = Field(default_factory=list)
    isolated_tables: List[str] = Field(default_factory=list)
    cycle_count: int = 0


class RelationshipGraphResponse(BaseModel):
    database_id: int
    database_name: str
    generated_at: datetime
    nodes: List[GraphNodeResponse] = Field(default_factory=list)
    edges: List[GraphEdgeResponse] = Field(default_factory=list)
    metrics: GraphMetricsResponse
    cycles: List[List[str]] = Field(default_factory=list)
    relationship_intelligence: Dict[str, Any] = Field(default_factory=dict)


class TableNeighborsResponse(BaseModel):
    table_id: int
    table_name: str
    schema_name: str
    neighbors: List[GraphNodeResponse] = Field(default_factory=list)
    edges: List[GraphEdgeResponse] = Field(default_factory=list)


class JoinStepResponse(BaseModel):
    source_table_id: int
    target_table_id: int
    source_table_name: str
    target_table_name: str
    relationship_type: str
    join_columns: List[JoinColumnResponse] = Field(default_factory=list)
    relationship_strength: float


class JoinPathResponse(BaseModel):
    source_table_id: int
    target_table_id: int
    hops: int
    steps: List[JoinStepResponse] = Field(default_factory=list)


class JoinPathsResponse(BaseModel):
    source_table_id: int
    target_table_id: int
    path_count: int
    paths: List[JoinPathResponse] = Field(default_factory=list)
    message: str = "Join paths discovered."


class GraphExportResponse(BaseModel):
    format: str
    filename: str
    content: str


class RelationshipPackageClusterResponse(BaseModel):
    cluster_id: str
    parent_cluster_id: Optional[str] = None
    domain_name: Optional[str] = None
    cluster_label: Optional[str] = None
    cluster_summary: Optional[str] = None
    cluster_confidence: float = 0.0
    entity_graph: List[Dict[str, Any]] = Field(default_factory=list)
    hidden_relationships: List[Dict[str, Any]] = Field(default_factory=list)
    business_process_flows: List[Dict[str, Any]] = Field(default_factory=list)
    upstream_dependencies: List[Dict[str, Any]] = Field(default_factory=list)
    downstream_dependencies: List[Dict[str, Any]] = Field(default_factory=list)
    lifecycle_flows: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    graph_metrics: Dict[str, Any] = Field(default_factory=dict)
    confidence_details: Dict[str, Any] = Field(default_factory=dict)
    estimated_tokens: Optional[int] = None
    actual_input_tokens: Optional[int] = None
    actual_output_tokens: Optional[int] = None
    prompt_truncated: Optional[bool] = None
    analysis_status: Optional[str] = None


class RelationshipPackageResponse(BaseModel):
    database_id: int
    packages: List[RelationshipPackageClusterResponse] = Field(default_factory=list)


class RelationshipLineageResponse(BaseModel):
    database_id: int
    lineage: List[Dict[str, Any]] = Field(default_factory=list)


# ── AI Readiness ───────────────────────────────────────────────────────────────

class ReadinessCapabilityScore(BaseModel):
    metadata_score: int
    semantic_score: int
    embeddings_score: int
    relationship_score: int
    prompt_score: int
    kpi_score: int = 0
    overall_score: int


class ReadinessCategoryScore(BaseModel):
    metadata_readiness_score: int
    semantic_readiness_score: int
    relationship_readiness_score: int
    ai_context_readiness_score: int
    governance_readiness_score: int
    kpi_readiness_score: int = 0
    overall_score: int
    kpi_cluster_count: int = 0
    successful_cluster_count: int = 0
    failed_cluster_count: int = 0
    coverage_percentage: float = 0.0
    kpi_cluster_count: int = 0
    successful_cluster_count: int = 0
    failed_cluster_count: int = 0
    coverage_percentage: float = 0.0


class ReadinessResponse(BaseModel):
    database_id: int
    database_name: str
    readiness_status: str
    generated_at: datetime
    scores: ReadinessCapabilityScore
    category_scores: ReadinessCategoryScore
    missing_stages: List[str] = Field(default_factory=list)
    remediation_hints: List[str] = Field(default_factory=list)
    prompt_id: Optional[str] = None
    prompt_version: Optional[str] = None
    model_name: Optional[str] = None
    kpi_cluster_count: int = 0
    successful_cluster_count: int = 0
    failed_cluster_count: int = 0
    coverage_percentage: float = 0.0


class ReadinessBreakdownResponse(ReadinessResponse):
    details: Dict[str, Any] = Field(default_factory=dict)
    ai_summary: Optional[str] = None
    ai_recommendations: List[str] = Field(default_factory=list)
    ai_risks: List[str] = Field(default_factory=list)
    ai_roadmap: List[str] = Field(default_factory=list)
    ai_confidence: float = 0.0


# ── Pipeline Operations ────────────────────────────────────────────────────────

class PipelineJobResponse(BaseModel):
    id: int
    job_type: str
    database_id: int
    parent_job_id: Optional[int] = None
    entity_table_id: Optional[int] = None
    entity_name: Optional[str] = None
    status: str
    progress_percentage: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    triggered_by: Optional[str] = None


class PipelineRunResponse(BaseModel):
    database_id: int
    created_job_ids: List[int] = Field(default_factory=list)
    message: str


class JobQueueResponse(BaseModel):
    database_id: int
    job_id: int
    job_type: str
    status: str
    message: str


# ── Database Semantics ────────────────────────────────────────────────────────

class GlossaryTerm(BaseModel):
    """A term in the business glossary."""
    term: str
    definition: str


class DatabaseSemanticGenerateRequest(BaseModel):
    """Request to generate database-level semantics."""
    # No additional fields needed - uses database metadata
    pass


class DatabaseSemanticResponse(BaseModel):
    """Response with database-level semantic profile."""
    id: int
    source_id: int
    business_domain: Optional[str] = None
    business_summary: Optional[str] = None
    analysis_notes: Optional[str] = None
    key_entities: List[str] = Field(default_factory=list)
    business_glossary: List[GlossaryTerm] = Field(default_factory=list)
    suggested_use_cases: List[str] = Field(default_factory=list)
    confidence_score: float = 0.0
    generation_status: str
    generated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SemanticEvidenceItemResponse(BaseModel):
    id: int
    semantic_package_id: int
    table_id: Optional[int] = None
    evidence_type: str
    evidence_source: str
    evidence_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class SemanticPackageResponse(BaseModel):
    database_id: int
    business_domain: Optional[str] = None
    semantic_summary: Optional[str] = None
    business_entities: List[str] = Field(default_factory=list)
    business_processes: List[str] = Field(default_factory=list)
    business_capabilities: List[str] = Field(default_factory=list)
    business_glossary: List[GlossaryTerm] = Field(default_factory=list)
    confidence_score: float = 0.0
    domain_scores: Dict[str, float] = Field(default_factory=dict)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    prompt_id: Optional[str] = None
    prompt_version: Optional[str] = None
    model_name: Optional[str] = None
    trace_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SemanticEvidenceResponse(BaseModel):
    database_id: int
    business_domain: Optional[str] = None
    confidence_score: float = 0.0
    domain_scores: Dict[str, float] = Field(default_factory=dict)
    evidence: List[SemanticEvidenceItemResponse] = Field(default_factory=list)


class DatabaseSemanticGenerateResponse(BaseModel):
    """Response for semantic generation request."""
    source_id: int
    status: str
    message: str
    generated_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    task_id: Optional[str] = None


class DatabaseSemanticExportResponse(BaseModel):
    """Response for semantic export."""
    format: str  # 'json' or 'markdown'
    filename: str
    content: str
    generated_at: datetime


# ── Artifact Registry ──────────────────────────────────────────────────────────

class ArtifactManifestItem(BaseModel):
    id: int
    artifact_type: str
    version: int
    schema_hash: str
    prompt_id: Optional[str] = None
    prompt_version: Optional[str] = None
    model_name: Optional[str] = None
    export_status: str
    artifact_path: str
    generated_at: datetime


class ArtifactListResponse(BaseModel):
    database_id: int
    artifacts: List[ArtifactManifestItem] = Field(default_factory=list)


class ArtifactManifestResponse(BaseModel):
    database_id: int
    artifact_count: int
    latest: Dict[str, ArtifactManifestItem] = Field(default_factory=dict)
    history: Dict[str, List[ArtifactManifestItem]] = Field(default_factory=dict)


class ArtifactExportResponse(BaseModel):
    database_id: int
    manifests: List[Dict[str, Any]] = Field(default_factory=list)
    message: str


class ArtifactContentResponse(BaseModel):
    id: int
    database_id: int
    artifact_type: str
    version: int
    schema_hash: str
    prompt_id: Optional[str] = None
    prompt_version: Optional[str] = None
    model_name: Optional[str] = None
    export_status: str
    artifact_path: str
    generated_at: datetime
    filename: str
    mime: str
    content: str


# â”€â”€ Prompt Studio â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class PromptStudioTemplateItem(BaseModel):
    id: str
    name: str
    description: str
    category: str
    version: str
    language: str
    path: str


class PromptStudioTemplateListResponse(BaseModel):
    templates: List[PromptStudioTemplateItem] = Field(default_factory=list)


class PromptGenerationRequest(BaseModel):
    database_id: int
    artifact_type: str
    template_id: str = "default"


class PromptOptimizationRequest(BaseModel):
    prompt_package_id: int


class PromptEvaluationRequest(BaseModel):
    prompt_package_id: int


class PromptInventoryItemResponse(BaseModel):
    prompt: str
    category: str
    executed: bool
    loaded_only: bool
    consumer: str


class PromptInventoryReportResponse(BaseModel):
    prompts: List[PromptInventoryItemResponse] = Field(default_factory=list)


class PromptStudioArtifactItem(BaseModel):
    artifact_type: str
    version: int
    schema_hash: Optional[str] = None
    prompt_id: Optional[str] = None
    prompt_version: Optional[str] = None
    model_name: Optional[str] = None
    export_status: Optional[str] = None
    artifact_path: Optional[str] = None
    filename: Optional[str] = None
    mime: str = "text/markdown"
    generated_at: Optional[datetime] = None


class PromptStudioArtifactResponse(BaseModel):
    database_id: int
    artifact_type: str
    filename: str
    mime: str
    content: str
    manifest: Optional[PromptStudioArtifactItem] = None
    generated_at: datetime


class PromptGenerationResponse(BaseModel):
    generated_prompt: str
    model: str
    trace_id: Optional[str] = None
    artifact_id: Optional[int] = None
    prompt_id: Optional[str] = None
    prompt_version: Optional[str] = None
    generated_at: Optional[datetime] = None


class PromptPackageResponse(BaseModel):
    id: int
    database_id: int
    artifact_type: str
    template_id: Optional[str] = None
    generated_prompt: str
    model_name: Optional[str] = None
    trace_id: Optional[str] = None
    prompt_version: Optional[str] = None
    confidence_score: float = 0.0
    generation_metadata: Optional[str] = None
    execution_status: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PromptVersionResponse(BaseModel):
    id: int
    prompt_package_id: int
    version: int
    generated_prompt: str
    model_name: Optional[str] = None
    template_id: Optional[str] = None
    trace_id: Optional[str] = None
    created_at: Optional[datetime] = None


class PromptObservabilityLogResponse(BaseModel):
    id: int
    prompt_package_id: int
    trace_id: Optional[str] = None
    model_name: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    latency_ms: Optional[float] = None
    finish_reason: Optional[str] = None
    execution_status: Optional[str] = None
    failure_reason: Optional[str] = None
    created_at: Optional[datetime] = None


class PromptEvaluationResponse(BaseModel):
    id: int
    prompt_package_id: int
    completeness_score: float
    safety_score: float
    grounding_score: float
    hallucination_risk: float
    sql_safety_score: float
    rag_quality_score: float
    agent_quality_score: float
    prompt_quality_score: float
    reasoning_summary: Optional[str] = None
    packages_used: str
    evidence: str
    trace_id: Optional[str] = None
    model_name: Optional[str] = None
    created_at: Optional[datetime] = None


class PromptPackageListResponse(BaseModel):
    database_id: int
    prompt_packages: List[PromptPackageResponse] = Field(default_factory=list)


class PromptVersionListResponse(BaseModel):
    prompt_package_id: int
    versions: List[PromptVersionResponse] = Field(default_factory=list)


class PromptObservabilityListResponse(BaseModel):
    prompt_package_id: int
    observability_logs: List[PromptObservabilityLogResponse] = Field(default_factory=list)


class PromptStudioBundleResponse(BaseModel):
    database_id: int
    bundle_filename: str
    bundle_mime: str = "application/json"
    content: str
    artifacts: List[PromptStudioArtifactResponse] = Field(default_factory=list)
    message: str


# ── Update forward refs ───────────────────────────────────────────────────────

ConnectionDetail.model_rebuild()
SchemaDetail.model_rebuild()
TableDetail.model_rebuild()
