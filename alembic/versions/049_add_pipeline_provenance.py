"""Add pipeline context provenance fields.

Revision ID: 049_add_pipeline_provenance
Revises: 048_add_token_observability
Create Date: 2026-06-17
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "049_add_pipeline_provenance"
down_revision = "048_add_token_observability"
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


def upgrade() -> None:
    columns = [
        sa.Column("pipeline_context_json", sa.Text(), nullable=True),
        sa.Column("context_source", sa.String(length=32), nullable=True),
        sa.Column("used_context", sa.Boolean(), nullable=True),
        sa.Column("fallback_reason", sa.Text(), nullable=True),
    ]
    for column in columns:
        _add_column_if_missing("pipeline_executions", column.copy())
        _add_column_if_missing("stage_executions", column.copy())


def downgrade() -> None:
    pass
