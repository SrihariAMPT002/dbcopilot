"""Add missing relationship graph fields and optional indexes.

Revision ID: 046_add_graph_fields_indexes
Revises: 045_add_lifecycle_workflows
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "046_add_graph_fields_indexes"
down_revision = "045_add_lifecycle_workflows"
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if table_name not in inspector.get_table_names():
        return
    existing = {item["name"] for item in inspector.get_columns(table_name)}
    if column.name not in existing:
        op.add_column(table_name, column)


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str], unique: bool = False) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if table_name not in inspector.get_table_names():
        return
    existing_indexes = inspector.get_indexes(table_name)
    existing_names = {index["name"] for index in existing_indexes}
    target_signature = (tuple(columns), bool(unique))
    existing_signatures = {
        (tuple(index.get("column_names") or []), bool(index.get("unique", False)))
        for index in existing_indexes
    }
    if index_name not in existing_names and target_signature not in existing_signatures:
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    # Relationship graph contract drift
    _add_column_if_missing("schema_relationship_graph", sa.Column("cluster_id", sa.String(length=128), nullable=True))
    _add_column_if_missing("schema_relationship_graph", sa.Column("parent_cluster_id", sa.String(length=128), nullable=True))
    _add_column_if_missing("schema_relationship_graph", sa.Column("domain_name", sa.String(length=255), nullable=True))
    _add_column_if_missing("schema_relationship_graph", sa.Column("cluster_size", sa.Integer(), nullable=True))
    _add_column_if_missing("schema_relationship_graph", sa.Column("cluster_confidence", sa.Float(), nullable=True))
    _add_column_if_missing("schema_relationship_graph", sa.Column("analysis_status", sa.String(length=64), nullable=True))

    # Optional performance indexes
    _create_index_if_missing("connected_databases", "ix_connected_databases_name", ["name"])
    _create_index_if_missing("connected_databases", "ix_connected_databases_db_type", ["db_type"])
    _create_index_if_missing("connected_databases", "ix_connected_databases_status", ["status"])
    _create_index_if_missing("connected_databases", "ix_connected_databases_lifecycle_status", ["lifecycle_status"])

    _create_index_if_missing("column_semantics", "ix_column_semantics_column_id", ["column_id"], unique=True)
    _create_index_if_missing("column_semantics", "ix_column_semantics_database_id", ["database_id"])
    _create_index_if_missing("column_semantics", "ix_column_semantics_execution_status", ["execution_status"])

    _create_index_if_missing("database_semantics", "ix_database_semantics_source_id", ["source_id"], unique=True)
    _create_index_if_missing("schema_semantics", "ix_schema_semantics_database_id", ["database_id"])
    _create_index_if_missing("schema_semantics", "ix_schema_semantics_table_id", ["table_id"])
    _create_index_if_missing("schema_embeddings", "ix_schema_embeddings_table_id", ["table_id"], unique=True)

    _create_index_if_missing("business_glossary", "ix_business_glossary_semantic_package_id", ["semantic_package_id"])
    _create_index_if_missing("semantic_evidence", "ix_semantic_evidence_semantic_package_id", ["semantic_package_id"])
    _create_index_if_missing("semantic_evidence", "ix_semantic_evidence_table_id", ["table_id"])
    _create_index_if_missing("pii_patterns", "ix_pii_patterns_pattern_key", ["pattern_key"], unique=True)
    _create_index_if_missing("column_statistics", "ix_column_statistics_column_id", ["column_id"], unique=True)

    _create_index_if_missing("stage_executions", "ix_stage_executions_database_id", ["database_id"])
    _create_index_if_missing("stage_executions", "ix_stage_executions_pipeline_execution_id", ["pipeline_execution_id"])
    _create_index_if_missing("stage_executions", "ix_stage_executions_status", ["status"])
    _create_index_if_missing("stage_executions", "ix_stage_executions_stage_name", ["stage_name"])

    _create_index_if_missing("schema_relationship_graph", "ix_schema_relationship_graph_cluster_id", ["cluster_id"])
    _create_index_if_missing("schema_relationship_graph", "ix_schema_relationship_graph_domain_name", ["domain_name"])
    _create_index_if_missing("schema_relationship_graph", "ix_schema_relationship_graph_parent_cluster_id", ["parent_cluster_id"])

    _create_index_if_missing("embedding_documents", "ix_embedding_documents_database_id", ["database_id"])
    _create_index_if_missing("embedding_documents", "ix_embedding_documents_document_type", ["document_type"])
    _create_index_if_missing("embedding_documents", "ix_embedding_documents_source_package", ["source_package"])
    _create_index_if_missing("embedding_documents", "ix_embedding_documents_vector_id", ["vector_id"])

    _create_index_if_missing("semantic_cache", "ix_semantic_cache_query_hash", ["query_hash"], unique=True)
    _create_index_if_missing("vector_collections", "ix_vector_collections_collection_name", ["collection_name"], unique=True)


def downgrade() -> None:
    # Intentionally no-op for additive safety.
    pass
