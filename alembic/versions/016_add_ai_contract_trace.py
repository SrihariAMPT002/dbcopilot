"""Add AI contract trace fields to persisted intelligence tables.

Revision ID: 016_add_ai_contract_trace
Revises: 015_add_readiness_ai_intel
Create Date: 2026-06-11
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "016_add_ai_contract_trace"
down_revision = "015_add_readiness_ai_intel"
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {item["name"] for item in inspector.get_columns(table_name)}
    if column.name not in existing:
        op.add_column(table_name, column)


def upgrade() -> None:
    # Column semantic contract fields.
    _add_column_if_missing("column_semantics", sa.Column("trace_id", sa.String(length=255), nullable=True))

    # Database semantic contract fields.
    _add_column_if_missing("database_semantics", sa.Column("execution_status", sa.String(length=64), nullable=True))
    _add_column_if_missing("database_semantics", sa.Column("used_fallback", sa.Boolean(), nullable=False, server_default=sa.false()))
    _add_column_if_missing("database_semantics", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
    _add_column_if_missing("database_semantics", sa.Column("trace_id", sa.String(length=255), nullable=True))

    # Relationship intelligence contract fields.
    _add_column_if_missing("schema_relationship_graph", sa.Column("trace_id", sa.String(length=255), nullable=True))

    # KPI contract fields.
    _add_column_if_missing("kpi_intelligence", sa.Column("trace_id", sa.String(length=255), nullable=True))

    # Readiness contract fields.
    _add_column_if_missing("readiness_snapshots", sa.Column("kpi_cluster_count", sa.Integer(), nullable=False, server_default="0"))
    _add_column_if_missing("readiness_snapshots", sa.Column("successful_cluster_count", sa.Integer(), nullable=False, server_default="0"))
    _add_column_if_missing("readiness_snapshots", sa.Column("failed_cluster_count", sa.Integer(), nullable=False, server_default="0"))
    _add_column_if_missing("readiness_snapshots", sa.Column("coverage_percentage", sa.Float(), nullable=False, server_default="0"))
    _add_column_if_missing("readiness_snapshots", sa.Column("execution_status", sa.String(length=64), nullable=True))
    _add_column_if_missing("readiness_snapshots", sa.Column("used_fallback", sa.Boolean(), nullable=False, server_default=sa.false()))
    _add_column_if_missing("readiness_snapshots", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
    _add_column_if_missing("readiness_snapshots", sa.Column("trace_id", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("readiness_snapshots", "trace_id")
    op.drop_column("readiness_snapshots", "retry_count")
    op.drop_column("readiness_snapshots", "used_fallback")
    op.drop_column("readiness_snapshots", "execution_status")
    op.drop_column("readiness_snapshots", "coverage_percentage")
    op.drop_column("readiness_snapshots", "failed_cluster_count")
    op.drop_column("readiness_snapshots", "successful_cluster_count")
    op.drop_column("readiness_snapshots", "kpi_cluster_count")

    op.drop_column("kpi_intelligence", "trace_id")

    op.drop_column("schema_relationship_graph", "trace_id")

    op.drop_column("database_semantics", "trace_id")
    op.drop_column("database_semantics", "retry_count")
    op.drop_column("database_semantics", "used_fallback")
    op.drop_column("database_semantics", "execution_status")

    op.drop_column("column_semantics", "trace_id")
