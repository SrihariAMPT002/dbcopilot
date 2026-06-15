"""Add missing telemetry columns to relationship_cluster_telemetry.

Revision ID: 025_add_telemetry_columns
Revises: 024_add_missing_cluster_columns
Create Date: 2026-06-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "025_add_telemetry_columns"
down_revision = "024_add_missing_cluster_columns"
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {item["name"] for item in inspector.get_columns(table_name)}
    if column.name not in existing:
        op.add_column(table_name, column)


def upgrade() -> None:
    _add_column_if_missing("relationship_cluster_telemetry", sa.Column("estimated_tokens", sa.Integer(), nullable=False, server_default="0"))
    _add_column_if_missing("relationship_cluster_telemetry", sa.Column("cluster_size", sa.Integer(), nullable=False, server_default="0"))
    _add_column_if_missing("relationship_cluster_telemetry", sa.Column("relationship_count", sa.Integer(), nullable=False, server_default="0"))
    _add_column_if_missing("relationship_cluster_telemetry", sa.Column("actual_input_tokens", sa.Integer(), nullable=False, server_default="0"))
    _add_column_if_missing("relationship_cluster_telemetry", sa.Column("actual_output_tokens", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("relationship_cluster_telemetry", "actual_output_tokens")
    op.drop_column("relationship_cluster_telemetry", "actual_input_tokens")
    op.drop_column("relationship_cluster_telemetry", "relationship_count")
    op.drop_column("relationship_cluster_telemetry", "cluster_size")
    op.drop_column("relationship_cluster_telemetry", "estimated_tokens")
