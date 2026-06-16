"""
SQLAlchemy ORM models for the internal metadata store.

Tables:
  connected_databases     — registered external data sources
  database_schemas        — schemas discovered inside each DB
  database_tables         — tables discovered inside each schema
  database_columns        — columns discovered inside each table
  database_relationships  — FK / join relationships between tables
  sync_logs               — audit log of every sync run
  schema_semantics        — AI-generated semantic enrichment data
  database_semantics      — AI-generated semantic enrichment data for databases
  schema_relationship_graph — graph-aware relationship edges for query planning
"""

import enum
import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ── Base ──────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── Enums ─────────────────────────────────────────────────────────────────────

class DatabaseType(str, enum.Enum):
    postgresql = "postgresql"
    mysql = "mysql"
    sqlserver = "sqlserver"
    mongodb = "mongodb"


class ConnectionStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    error = "error"
    testing = "testing"


class DatabaseLifecycleStatus(str, enum.Enum):
    active = "ACTIVE"
    disconnected = "DISCONNECTED"
    archived = "ARCHIVED"
    deleted = "DELETED"


class SyncStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"


class EmbeddingStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class TableType(str, enum.Enum):
    table = "table"
    view = "view"
    materialized_view = "materialized_view"
    foreign_table = "foreign_table"


class SemanticGenerationStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    no_metadata = "no_metadata"


# ── Models ────────────────────────────────────────────────────────────────────

class ConnectedDatabase(Base):
    """A registered external data source."""
    __tablename__ = "connected_databases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    db_type: Mapped[DatabaseType] = mapped_column(
        Enum(DatabaseType, name="database_type_enum"), nullable=False, index=True
    )
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    database_name: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_password: Mapped[str] = mapped_column(Text, nullable=False)
    ssl_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Status
    status: Mapped[ConnectionStatus] = mapped_column(
        Enum(ConnectionStatus, name="connection_status_enum"),
        default=ConnectionStatus.inactive,
        nullable=False,
        index=True,
    )
    lifecycle_status: Mapped[DatabaseLifecycleStatus] = mapped_column(
        Enum(
            DatabaseLifecycleStatus,
            name="database_lifecycle_status_enum",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=DatabaseLifecycleStatus.active,
        nullable=False,
        index=True,
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    disconnected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    disconnected_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deletion_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships (lazy="raise" prevents accidental lazy-loads in async context)
    schemas: Mapped[List["DatabaseSchema"]] = relationship(
        "DatabaseSchema",
        back_populates="connected_database",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    sync_logs: Mapped[List["SyncLog"]] = relationship(
        "SyncLog",
        back_populates="connected_database",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    lifecycle_events: Mapped[List["DatabaseLifecycleEvent"]] = relationship(
        "DatabaseLifecycleEvent",
        back_populates="connected_database",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<ConnectedDatabase id={self.id} name={self.name!r} type={self.db_type}>"


class DatabaseLifecycleEvent(Base):
    """Audit trail for database lifecycle transitions."""

    __tablename__ = "database_lifecycle_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    connected_db_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    connected_database: Mapped["ConnectedDatabase"] = relationship(
        "ConnectedDatabase", back_populates="lifecycle_events", lazy="raise"
    )


class DatabaseSchema(Base):
    """A schema/namespace discovered within a connected database."""
    __tablename__ = "database_schemas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    connected_db_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    connected_database: Mapped["ConnectedDatabase"] = relationship(
        "ConnectedDatabase", back_populates="schemas", lazy="raise"
    )
    tables: Mapped[List["DatabaseTable"]] = relationship(
        "DatabaseTable",
        back_populates="schema",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<DatabaseSchema id={self.id} name={self.name!r}>"


class DatabaseTable(Base):
    """A table or view discovered within a schema."""
    __tablename__ = "database_tables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schema_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("database_schemas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    table_type: Mapped[TableType] = mapped_column(
        Enum(TableType, name="table_type_enum"),
        default=TableType.table,
        nullable=False,
    )
    row_count: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    schema: Mapped["DatabaseSchema"] = relationship(
        "DatabaseSchema", back_populates="tables", lazy="raise"
    )
    columns: Mapped[List["DatabaseColumn"]] = relationship(
        "DatabaseColumn",
        back_populates="table",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    embedding: Mapped[Optional["SchemaEmbedding"]] = relationship(
        "SchemaEmbedding",
        back_populates="table",
        cascade="all, delete-orphan",
        single_parent=True,
        uselist=False,
        lazy="raise",
    )
    # Relationships where this table is the source (explicit join to disambiguate multiple FKs)
    relationships_from: Mapped[List["DatabaseRelationship"]] = relationship(
        "DatabaseRelationship",
        primaryjoin="DatabaseTable.id == DatabaseRelationship.table_id",
        back_populates="table",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<DatabaseTable id={self.id} name={self.name!r} type={self.table_type}>"


class DatabaseColumn(Base):
    """A column within a table."""
    __tablename__ = "database_columns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("database_tables.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    data_type: Mapped[str] = mapped_column(String(255), nullable=False)
    ordinal_position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_nullable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_primary_key: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_foreign_key: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_unique: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_indexed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    max_length: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    table: Mapped["DatabaseTable"] = relationship(
        "DatabaseTable", back_populates="columns", lazy="raise"
    )

    def __repr__(self) -> str:
        return f"<DatabaseColumn id={self.id} name={self.name!r} type={self.data_type}>"


class DatabaseRelationship(Base):
    """A foreign-key relationship between two tables."""
    __tablename__ = "database_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Source
    table_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("database_tables.id", ondelete="CASCADE"), nullable=False, index=True
    )
    column_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Target
    referenced_table_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("database_tables.id", ondelete="SET NULL"), nullable=True
    )
    referenced_schema: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    referenced_table_name: Mapped[str] = mapped_column(String(255), nullable=False)
    referenced_column_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Constraint name (if available from the source DB)
    constraint_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    table: Mapped["DatabaseTable"] = relationship(
        "DatabaseTable",
        primaryjoin="DatabaseRelationship.table_id == DatabaseTable.id",
        back_populates="relationships_from",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return (
            f"<DatabaseRelationship "
            f"{self.column_name!r} → {self.referenced_table_name!r}.{self.referenced_column_name!r}>"
        )


class SyncLog(Base):
    """Audit log for every schema synchronization run."""
    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    connected_db_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[SyncStatus] = mapped_column(
        Enum(SyncStatus, name="sync_status_enum"),
        default=SyncStatus.pending,
        nullable=False,
        index=True,
    )
    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[Optional[float]] = mapped_column(nullable=True)
    # Counts
    schemas_synced: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tables_synced: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    columns_synced: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    relationships_synced: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Error info
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    connected_database: Mapped["ConnectedDatabase"] = relationship(
        "ConnectedDatabase", back_populates="sync_logs", lazy="raise"
    )

    def __repr__(self) -> str:
        return f"<SyncLog id={self.id} db_id={self.connected_db_id} status={self.status}>"


class SchemaSemantic(Base):
    """
    Semantic enrichment data for tables.
    
    Stores AI-generated business context:
    - Business summary
    - Likely usage patterns
    - Important columns
    - Business keywords
    - Possible analytics questions
    
    List fields are stored as JSON strings for compatibility.
    """
    __tablename__ = "schema_semantics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    database_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    table_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("database_tables.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    # Semantic enrichment data (all generated by AI)
    semantic_summary: Mapped[str] = mapped_column(Text, nullable=False)

    
    # Store lists as JSON strings for compatibility with all databases
    _likely_usage: Mapped[str] = mapped_column("likely_usage", Text, nullable=False, default="[]")
    _important_columns: Mapped[str] = mapped_column("important_columns", Text, nullable=False, default="[]")
    _business_keywords: Mapped[str] = mapped_column("business_keywords", Text, nullable=False, default="[]")
    _possible_questions: Mapped[str] = mapped_column("possible_questions", Text, nullable=False, default="[]")
    _business_processes: Mapped[str] = mapped_column("business_processes", Text, nullable=False, default="[]")

    # Metadata
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # ── Properties for JSON serialization/deserialization ──────────────────

    @property
    def likely_usage(self) -> list[str]:
        """Deserialize likely_usage from JSON string."""
        try:
            return json.loads(self._likely_usage) if self._likely_usage else []
        except (json.JSONDecodeError, TypeError):
            return []

    @likely_usage.setter
    def likely_usage(self, value: list[str]) -> None:
        """Serialize likely_usage to JSON string."""
        self._likely_usage = json.dumps(value or [])

    @property
    def important_columns(self) -> list[str]:
        """Deserialize important_columns from JSON string."""
        try:
            return json.loads(self._important_columns) if self._important_columns else []
        except (json.JSONDecodeError, TypeError):
            return []

    @important_columns.setter
    def important_columns(self, value: list[str]) -> None:
        """Serialize important_columns to JSON string."""
        self._important_columns = json.dumps(value or [])

    @property
    def business_keywords(self) -> list[str]:
        """Deserialize business_keywords from JSON string."""
        try:
            return json.loads(self._business_keywords) if self._business_keywords else []
        except (json.JSONDecodeError, TypeError):
            return []

    @business_keywords.setter
    def business_keywords(self, value: list[str]) -> None:
        """Serialize business_keywords to JSON string."""
        self._business_keywords = json.dumps(value or [])

    @property
    def possible_questions(self) -> list[str]:
        """Deserialize possible_questions from JSON string."""
        try:
            return json.loads(self._possible_questions) if self._possible_questions else []
        except (json.JSONDecodeError, TypeError):
            return []

    @possible_questions.setter
    def possible_questions(self, value: list[str]) -> None:
        """Serialize possible_questions to JSON string."""
        self._possible_questions = json.dumps(value or [])

    @property
    def business_capabilities(self) -> list[str]:
        return self.likely_usage

    @business_capabilities.setter
    def business_capabilities(self, value: list[str]) -> None:
        self.likely_usage = value

    @property
    def business_entities(self) -> list[str]:
        return self.important_columns

    @business_entities.setter
    def business_entities(self, value: list[str]) -> None:
        self.important_columns = value

    @property
    def business_processes(self) -> list[str]:
        try:
            return json.loads(self._business_processes) if self._business_processes else []
        except (json.JSONDecodeError, TypeError):
            return []

    @business_processes.setter
    def business_processes(self, value: list[str]) -> None:
        self._business_processes = json.dumps(value or [])

    def __repr__(self) -> str:
        return f"<SchemaSemantic id={self.id} table_id={self.table_id}>"


class SchemaEmbedding(Base):
    """Track vector indexing status for a table."""

    __tablename__ = "schema_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("database_tables.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    vector_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    embedded_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding_status: Mapped[EmbeddingStatus] = mapped_column(
        Enum(EmbeddingStatus, name="embedding_status_enum"),
        default=EmbeddingStatus.pending,
        nullable=False,
        index=True,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    table: Mapped["DatabaseTable"] = relationship(
        "DatabaseTable",
        back_populates="embedding",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<SchemaEmbedding id={self.id} table_id={self.table_id} status={self.embedding_status}>"


class SchemaRelationshipGraph(Base):
    """Graph-aware relationship edge persisted for traversal and query planning."""

    __tablename__ = "schema_relationship_graph"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    database_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("connected_databases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_table_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("database_tables.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_table_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("database_tables.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_table_name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_table_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_schema_name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_schema_name: Mapped[str] = mapped_column(String(255), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    join_columns: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    relationship_strength: Mapped[float] = mapped_column(nullable=False, default=1.0)
    path_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_circular: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    business_entity_graph: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    business_process_flows: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    upstream_dependencies: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    downstream_dependencies: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    entity_lifecycle_descriptions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_confidence: Mapped[Optional[float]] = mapped_column(nullable=True)
    ai_model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ai_prompt_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ai_prompt_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    cluster_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    parent_cluster_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    domain_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    cluster_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    estimated_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actual_input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actual_output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cluster_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cluster_confidence: Mapped[Optional[float]] = mapped_column(nullable=True)
    prompt_truncated: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    analysis_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    execution_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    used_fallback: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    @property
    def entity_graph(self) -> list[dict]:
        try:
            return json.loads(self.business_entity_graph) if self.business_entity_graph else []
        except (json.JSONDecodeError, TypeError):
            return []

    @entity_graph.setter
    def entity_graph(self, value: list[dict]) -> None:
        self.business_entity_graph = json.dumps(value or [])

    @property
    def business_entity_graph_alias(self) -> list[dict]:
        return self.entity_graph

    @business_entity_graph_alias.setter
    def business_entity_graph_alias(self, value: list[dict]) -> None:
        self.entity_graph = value

    @property
    def lifecycle_flows(self) -> list[dict]:
        try:
            return json.loads(self.entity_lifecycle_descriptions) if self.entity_lifecycle_descriptions else []
        except (json.JSONDecodeError, TypeError):
            return []

    @lifecycle_flows.setter
    def lifecycle_flows(self, value: list[dict]) -> None:
        self.entity_lifecycle_descriptions = json.dumps(value or [])

    @property
    def entity_lifecycle_descriptions_alias(self) -> list[dict]:
        return self.lifecycle_flows

    @entity_lifecycle_descriptions_alias.setter
    def entity_lifecycle_descriptions_alias(self, value: list[dict]) -> None:
        self.lifecycle_flows = value
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    source_table: Mapped["DatabaseTable"] = relationship(
        "DatabaseTable",
        primaryjoin="SchemaRelationshipGraph.source_table_id == DatabaseTable.id",
        lazy="raise",
    )
    target_table: Mapped["DatabaseTable"] = relationship(
        "DatabaseTable",
        primaryjoin="SchemaRelationshipGraph.target_table_id == DatabaseTable.id",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return (
            "<SchemaRelationshipGraph "
            f"{self.source_schema_name}.{self.source_table_name} -> "
            f"{self.target_schema_name}.{self.target_table_name}>"
        )


class GovernancePackage(Base):
    """Persisted canonical governance package for a table."""

    __tablename__ = "governance_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    database_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("connected_databases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    table_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("database_tables.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    table_name: Mapped[str] = mapped_column(String(255), nullable=False)
    schema_name: Mapped[str] = mapped_column(String(255), nullable=False)
    table_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    business_purpose: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    _pii_columns: Mapped[str] = mapped_column("pii_columns", Text, nullable=False, default="[]")
    _risk_columns: Mapped[str] = mapped_column("risk_columns", Text, nullable=False, default="[]")
    _sensitive_columns: Mapped[str] = mapped_column("sensitive_columns", Text, nullable=False, default="[]")
    overall_risk: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    confidence_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    evidence: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    rule_matches: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    sample_patterns: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reasoning_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    finish_reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    latency_ms: Mapped[Optional[float]] = mapped_column(nullable=True)
    prompt_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    raw_failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    @property
    def pii_columns(self) -> list[dict]:
        try:
            return json.loads(self._pii_columns) if self._pii_columns else []
        except (json.JSONDecodeError, TypeError):
            return []

    @pii_columns.setter
    def pii_columns(self, value: list[dict]) -> None:
        self._pii_columns = json.dumps(value or [])

    @property
    def risk_columns(self) -> list[dict]:
        try:
            return json.loads(self._risk_columns) if self._risk_columns else []
        except (json.JSONDecodeError, TypeError):
            return []

    @risk_columns.setter
    def risk_columns(self, value: list[dict]) -> None:
        self._risk_columns = json.dumps(value or [])

    @property
    def sensitive_columns(self) -> list[dict]:
        try:
            return json.loads(self._sensitive_columns) if self._sensitive_columns else []
        except (json.JSONDecodeError, TypeError):
            return []

    @sensitive_columns.setter
    def sensitive_columns(self, value: list[dict]) -> None:
        self._sensitive_columns = json.dumps(value or [])

    @property
    def failure_reason(self) -> Optional[str]:
        return self.raw_failure_reason

    @failure_reason.setter
    def failure_reason(self, value: Optional[str]) -> None:
        self.raw_failure_reason = value


class GovernanceEvidence(Base):
    __tablename__ = "governance_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    governance_package_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("governance_packages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    column_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("database_columns.id", ondelete="CASCADE"), nullable=True, index=True
    )
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_source: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ColumnStatistics(Base):
    __tablename__ = "column_statistics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    database_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    table_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("database_tables.id", ondelete="CASCADE"), nullable=False, index=True
    )
    column_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("database_columns.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    column_name: Mapped[str] = mapped_column(String(255), nullable=False)
    data_type: Mapped[str] = mapped_column(String(255), nullable=False)
    stats_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PIIPattern(Base):
    __tablename__ = "pii_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pattern_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    pattern_type: Mapped[str] = mapped_column(String(32), nullable=False)
    pattern_value: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    confidence_weight: Mapped[float] = mapped_column(nullable=False, default=0.5)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DatabaseSemantic(Base):
    """
    Database-level semantic enrichment.
    
    Stores AI-generated business context for entire databases:
    - Business domain
    - Business summary
    - Key entities
    - Business glossary
    - Suggested use cases
    - Analysis notes (caveats and uncertainty from generation)
    - Confidence score
    
    Generation status tracks the state of semantic generation.
    """
    __tablename__ = "database_semantics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    # Semantic enrichment data (generated by AI)
    business_domain: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    business_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    analysis_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Store lists and structured data as JSON strings for compatibility
    _key_entities: Mapped[str] = mapped_column("key_entities", Text, nullable=False, default="[]")
    _business_glossary: Mapped[str] = mapped_column("business_glossary", Text, nullable=False, default="[]")
    _suggested_use_cases: Mapped[str] = mapped_column("suggested_use_cases", Text, nullable=False, default="[]")
    _business_processes: Mapped[str] = mapped_column("business_processes", Text, nullable=False, default="[]")

    # Confidence and metadata
    confidence_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    generation_status: Mapped[SemanticGenerationStatus] = mapped_column(
        Enum(SemanticGenerationStatus, name="semantic_generation_status_enum"),
        default=SemanticGenerationStatus.pending,
        nullable=False,
        index=True,
    )
    execution_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    used_fallback: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Store raw AI response for debugging/transparency
    raw_ai_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timing
    generated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # ── Properties for JSON serialization/deserialization ──────────────────

    @property
    def key_entities(self) -> list[str]:
        """Deserialize key_entities from JSON string."""
        try:
            return json.loads(self._key_entities) if self._key_entities else []
        except (json.JSONDecodeError, TypeError):
            return []

    @key_entities.setter
    def key_entities(self, value: list[str]) -> None:
        """Serialize key_entities to JSON string."""
        self._key_entities = json.dumps(value or [])

    @property
    def business_glossary(self) -> list[dict]:
        """Deserialize business_glossary from JSON string."""
        try:
            return json.loads(self._business_glossary) if self._business_glossary else []
        except (json.JSONDecodeError, TypeError):
            return []

    @business_glossary.setter
    def business_glossary(self, value: list[dict]) -> None:
        """Serialize business_glossary to JSON string."""
        self._business_glossary = json.dumps(value or [])

    @property
    def suggested_use_cases(self) -> list[str]:
        """Deserialize suggested_use_cases from JSON string."""
        try:
            return json.loads(self._suggested_use_cases) if self._suggested_use_cases else []
        except (json.JSONDecodeError, TypeError):
            return []

    @suggested_use_cases.setter
    def suggested_use_cases(self, value: list[str]) -> None:
        """Serialize suggested_use_cases to JSON string."""
        self._suggested_use_cases = json.dumps(value or [])

    @property
    def business_capabilities(self) -> list[str]:
        return self.suggested_use_cases

    @business_capabilities.setter
    def business_capabilities(self, value: list[str]) -> None:
        self.suggested_use_cases = value

    @property
    def business_entities(self) -> list[str]:
        return self.key_entities

    @business_entities.setter
    def business_entities(self, value: list[str]) -> None:
        self.key_entities = value

    @property
    def business_processes(self) -> list[str]:
        try:
            return json.loads(self._business_processes) if self._business_processes else []
        except (json.JSONDecodeError, TypeError):
            return []

    @business_processes.setter
    def business_processes(self, value: list[str]) -> None:
        self._business_processes = json.dumps(value or [])

    @property
    def semantic_summary(self) -> str | None:
        return self.business_summary

    @semantic_summary.setter
    def semantic_summary(self, value: str | None) -> None:
        self.business_summary = value


class SemanticPackage(Base):
    """Persisted canonical semantic package for a database."""

    __tablename__ = "semantic_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    database_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    business_domain: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    semantic_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    _business_entities: Mapped[str] = mapped_column("business_entities", Text, nullable=False, default="[]")
    _business_processes: Mapped[str] = mapped_column("business_processes", Text, nullable=False, default="[]")
    _business_capabilities: Mapped[str] = mapped_column("business_capabilities", Text, nullable=False, default="[]")
    _business_glossary: Mapped[str] = mapped_column("business_glossary", Text, nullable=False, default="[]")
    confidence_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    _domain_scores: Mapped[str] = mapped_column("domain_scores", Text, nullable=False, default="{}")
    _evidence: Mapped[str] = mapped_column("evidence", Text, nullable=False, default="[]")
    prompt_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    @property
    def business_entities(self) -> list[str]:
        try:
            return json.loads(self._business_entities) if self._business_entities else []
        except (json.JSONDecodeError, TypeError):
            return []

    @business_entities.setter
    def business_entities(self, value: list[str]) -> None:
        self._business_entities = json.dumps(value or [])

    @property
    def business_processes(self) -> list[str]:
        try:
            return json.loads(self._business_processes) if self._business_processes else []
        except (json.JSONDecodeError, TypeError):
            return []

    @business_processes.setter
    def business_processes(self, value: list[str]) -> None:
        self._business_processes = json.dumps(value or [])

    @property
    def business_capabilities(self) -> list[str]:
        try:
            return json.loads(self._business_capabilities) if self._business_capabilities else []
        except (json.JSONDecodeError, TypeError):
            return []

    @business_capabilities.setter
    def business_capabilities(self, value: list[str]) -> None:
        self._business_capabilities = json.dumps(value or [])

    @property
    def business_glossary(self) -> list[dict]:
        try:
            return json.loads(self._business_glossary) if self._business_glossary else []
        except (json.JSONDecodeError, TypeError):
            return []

    @business_glossary.setter
    def business_glossary(self, value: list[dict]) -> None:
        self._business_glossary = json.dumps(value or [])

    @property
    def domain_scores(self) -> dict:
        try:
            return json.loads(self._domain_scores) if self._domain_scores else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    @domain_scores.setter
    def domain_scores(self, value: dict) -> None:
        self._domain_scores = json.dumps(value or {})

    @property
    def evidence(self) -> list[dict]:
        try:
            return json.loads(self._evidence) if self._evidence else []
        except (json.JSONDecodeError, TypeError):
            return []

    @evidence.setter
    def evidence(self, value: list[dict]) -> None:
        self._evidence = json.dumps(value or [])


class TableSemanticPackage(Base):
    """Persisted canonical semantic package for a table."""

    __tablename__ = "table_semantic_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    database_id: Mapped[int] = mapped_column(Integer, ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False, index=True)
    table_id: Mapped[int] = mapped_column(Integer, ForeignKey("database_tables.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    business_purpose: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    business_entity: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    business_capability: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    business_process: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    _business_keywords: Mapped[str] = mapped_column("business_keywords", Text, nullable=False, default="[]")
    _evidence: Mapped[str] = mapped_column("evidence", Text, nullable=False, default="[]")
    semantic_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    prompt_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    @property
    def business_keywords(self) -> list[str]:
        try:
            return json.loads(self._business_keywords) if self._business_keywords else []
        except (json.JSONDecodeError, TypeError):
            return []

    @business_keywords.setter
    def business_keywords(self, value: list[str]) -> None:
        self._business_keywords = json.dumps(value or [])

    @property
    def evidence(self) -> list[dict]:
        try:
            return json.loads(self._evidence) if self._evidence else []
        except (json.JSONDecodeError, TypeError):
            return []

    @evidence.setter
    def evidence(self, value: list[dict]) -> None:
        self._evidence = json.dumps(value or [])


class SemanticEvidence(Base):
    __tablename__ = "semantic_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    semantic_package_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("semantic_packages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    table_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("database_tables.id", ondelete="CASCADE"), nullable=True, index=True)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_source: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BusinessGlossary(Base):
    __tablename__ = "business_glossary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    semantic_package_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("semantic_packages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    term: Mapped[str] = mapped_column(String(255), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="ai")
    confidence_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RelationshipPackage(Base):
    """Persisted canonical relationship intelligence package."""

    __tablename__ = "relationship_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    database_id: Mapped[int] = mapped_column(Integer, ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False, index=True)
    cluster_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    domain_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cluster_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    _entity_graph: Mapped[str] = mapped_column("entity_graph", Text, nullable=False, default="[]")
    _business_process_flows: Mapped[str] = mapped_column("business_process_flows", Text, nullable=False, default="[]")
    _hidden_relationships: Mapped[str] = mapped_column("hidden_relationships", Text, nullable=False, default="[]")
    _upstream_dependencies: Mapped[str] = mapped_column("upstream_dependencies", Text, nullable=False, default="[]")
    _downstream_dependencies: Mapped[str] = mapped_column("downstream_dependencies", Text, nullable=False, default="[]")
    _lifecycle_flows: Mapped[str] = mapped_column("lifecycle_flows", Text, nullable=False, default="[]")
    _evidence: Mapped[str] = mapped_column("evidence", Text, nullable=False, default="[]")
    _graph_metrics: Mapped[str] = mapped_column("graph_metrics", Text, nullable=False, default="{}")
    _confidence_details: Mapped[str] = mapped_column("confidence_details", Text, nullable=False, default="{}")
    confidence_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    prompt_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    @property
    def entity_graph(self) -> list[dict]:
        try:
            return json.loads(self._entity_graph) if self._entity_graph else []
        except (json.JSONDecodeError, TypeError):
            return []

    @entity_graph.setter
    def entity_graph(self, value: list[dict]) -> None:
        self._entity_graph = json.dumps(value or [])

    @property
    def business_process_flows(self) -> list[dict]:
        try:
            return json.loads(self._business_process_flows) if self._business_process_flows else []
        except (json.JSONDecodeError, TypeError):
            return []

    @business_process_flows.setter
    def business_process_flows(self, value: list[dict]) -> None:
        self._business_process_flows = json.dumps(value or [])

    @property
    def hidden_relationships(self) -> list[dict]:
        try:
            return json.loads(self._hidden_relationships) if self._hidden_relationships else []
        except (json.JSONDecodeError, TypeError):
            return []

    @hidden_relationships.setter
    def hidden_relationships(self, value: list[dict]) -> None:
        self._hidden_relationships = json.dumps(value or [])

    @property
    def upstream_dependencies(self) -> list[dict]:
        try:
            return json.loads(self._upstream_dependencies) if self._upstream_dependencies else []
        except (json.JSONDecodeError, TypeError):
            return []

    @upstream_dependencies.setter
    def upstream_dependencies(self, value: list[dict]) -> None:
        self._upstream_dependencies = json.dumps(value or [])

    @property
    def downstream_dependencies(self) -> list[dict]:
        try:
            return json.loads(self._downstream_dependencies) if self._downstream_dependencies else []
        except (json.JSONDecodeError, TypeError):
            return []

    @downstream_dependencies.setter
    def downstream_dependencies(self, value: list[dict]) -> None:
        self._downstream_dependencies = json.dumps(value or [])

    @property
    def lifecycle_flows(self) -> list[dict]:
        try:
            return json.loads(self._lifecycle_flows) if self._lifecycle_flows else []
        except (json.JSONDecodeError, TypeError):
            return []

    @lifecycle_flows.setter
    def lifecycle_flows(self, value: list[dict]) -> None:
        self._lifecycle_flows = json.dumps(value or [])

    @property
    def evidence(self) -> list[dict]:
        try:
            return json.loads(self._evidence) if self._evidence else []
        except (json.JSONDecodeError, TypeError):
            return []

    @evidence.setter
    def evidence(self, value: list[dict]) -> None:
        self._evidence = json.dumps(value or [])

    @property
    def graph_metrics(self) -> dict:
        try:
            return json.loads(self._graph_metrics) if self._graph_metrics else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    @graph_metrics.setter
    def graph_metrics(self, value: dict) -> None:
        self._graph_metrics = json.dumps(value or {})

    @property
    def confidence_details(self) -> dict:
        try:
            return json.loads(self._confidence_details) if self._confidence_details else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    @confidence_details.setter
    def confidence_details(self, value: dict) -> None:
        self._confidence_details = json.dumps(value or {})

    @property
    def cluster_confidence(self) -> float:
        """Backward-compatible alias for the canonical confidence score."""
        return float(self.confidence_score or 0.0)

    @cluster_confidence.setter
    def cluster_confidence(self, value: float) -> None:
        self.confidence_score = float(value or 0.0)

    @property
    def failure_reason(self) -> Optional[str]:
        """Backward-compatible alias for the raw failure reason."""
        return self.raw_failure_reason

    @failure_reason.setter
    def failure_reason(self, value: Optional[str]) -> None:
        self.raw_failure_reason = value


class RelationshipClusterTelemetry(Base):
    """Telemetry for cluster analysis and prompt stability."""

    __tablename__ = "relationship_cluster_telemetry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    database_id: Mapped[int] = mapped_column(Integer, ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False, index=True)
    cluster_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    domain_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cluster_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    relationship_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actual_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actual_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt_truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    finish_reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    response_quality: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    prompt_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RelationshipEvidence(Base):
    __tablename__ = "relationship_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    relationship_package_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("relationship_packages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cluster_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_source: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ClusterScore(Base):
    __tablename__ = "cluster_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    relationship_package_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("relationship_packages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cluster_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    centrality_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    hub_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    community_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    confidence_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class KPIIntelligence(Base):
    """Canonical KPI intelligence records discovered from metadata."""

    __tablename__ = "kpi_intelligence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    database_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prompt_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    business_meaning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    formula: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_tables: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_columns: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dimensions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    filters: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(nullable=False, default=0.0)
    owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    lineage_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    discovery_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    package_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    confidence_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    metadata_fingerprint: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="discovered", index=True)
    cluster_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    cluster_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cluster_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    estimated_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actual_input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actual_output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    execution_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    used_fallback: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class KPIArtifact(Base):
    """Versioned KPI artifact manifest for generated KPI outputs."""

    __tablename__ = "kpi_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    database_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prompt_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    artifact_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    schema_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    confidence_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    metadata_fingerprint: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    artifact_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime: Mapped[str] = mapped_column(String(128), nullable=False, default="application/json")
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<DatabaseSemantic id={self.id} source_id={self.source_id} status={self.generation_status}>"

