"""Add subcluster and domain fields to schema_relationship_graph.

Revision ID: 018_add_subcluster_fields
Revises: 016_add_ai_contract_trace
Create Date: 2026-06-11
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "018_add_subcluster_fields"
down_revision = "017_add__semantics_fields"
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {item["name"] for item in inspector.get_columns(table_name)}
    if column.name not in existing:
        op.add_column(table_name, column)


def upgrade() -> None:
    _add_column_if_missing("schema_relationship_graph", sa.Column("parent_cluster_id", sa.String(length=128), nullable=True))
    _add_column_if_missing("schema_relationship_graph", sa.Column("domain_name", sa.String(length=255), nullable=True))
    _add_column_if_missing("schema_relationship_graph", sa.Column("prompt_truncated", sa.Boolean(), nullable=True))
    _add_column_if_missing("schema_relationship_graph", sa.Column("analysis_status", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("schema_relationship_graph", "analysis_status")
    op.drop_column("schema_relationship_graph", "prompt_truncated")
    op.drop_column("schema_relationship_graph", "domain_name")
    op.drop_column("schema_relationship_graph", "parent_cluster_id")
