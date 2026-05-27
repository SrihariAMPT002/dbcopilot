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


# ── Update forward refs ───────────────────────────────────────────────────────

ConnectionDetail.model_rebuild()
SchemaDetail.model_rebuild()
TableDetail.model_rebuild()
