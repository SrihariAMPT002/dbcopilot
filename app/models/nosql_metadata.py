"""
NoSQL metadata models for schema inference and semantic readiness.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.metadata import Base


class NoSQLCollection(Base):
    __tablename__ = "nosql_collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    database_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("connected_databases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    schema_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("database_schemas.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    table_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("database_tables.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    document_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sampled_documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    schema_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    inferred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class NoSQLSchemaField(Base):
    __tablename__ = "nosql_schema_fields"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collection_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("nosql_collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_path: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    inferred_data_type: Mapped[str] = mapped_column(String(128), nullable=False)
    nested_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_array: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    occurrence_percentage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    schema_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    type_distribution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    inferred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class NoSQLDocumentSample(Base):
    __tablename__ = "nosql_document_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collection_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("nosql_collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sample_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sample_document: Mapped[str] = mapped_column(Text, nullable=False)
    sampled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class NoSQLRelationship(Base):
    __tablename__ = "nosql_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collection_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("nosql_collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    related_collection_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("nosql_collections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_field_path: Mapped[str] = mapped_column(String(512), nullable=False)
    target_collection_name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_field_path: Mapped[str] = mapped_column(String(255), nullable=False, default="_id")
    relationship_type: Mapped[str] = mapped_column(String(64), nullable=False, default="inferred_ref")
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inferred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
