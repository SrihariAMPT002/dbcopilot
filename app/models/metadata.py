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
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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

    def __repr__(self) -> str:
        return f"<ConnectedDatabase id={self.id} name={self.name!r} type={self.db_type}>"


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
    prompt_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Store lists as JSON strings for compatibility with all databases
    _likely_usage: Mapped[str] = mapped_column("likely_usage", Text, nullable=False, default="[]")
    _important_columns: Mapped[str] = mapped_column("important_columns", Text, nullable=False, default="[]")
    _business_keywords: Mapped[str] = mapped_column("business_keywords", Text, nullable=False, default="[]")
    _possible_questions: Mapped[str] = mapped_column("possible_questions", Text, nullable=False, default="[]")

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

    # Confidence and metadata
    confidence_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    generation_status: Mapped[SemanticGenerationStatus] = mapped_column(
        Enum(SemanticGenerationStatus, name="semantic_generation_status_enum"),
        default=SemanticGenerationStatus.pending,
        nullable=False,
        index=True,
    )
    
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

    def __repr__(self) -> str:
        return f"<DatabaseSemantic id={self.id} source_id={self.source_id} status={self.generation_status}>"

