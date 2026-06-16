"""Add token observability columns to execution and prompt logs.

Revision ID: 048_add_token_observability
Revises: 047_add_database_id_logs
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "048_add_token_observability"
down_revision = "047_add_database_id_logs"
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
    token_columns = [
        sa.Column("estimated_input_tokens", sa.Integer(), nullable=True),
        sa.Column("actual_input_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_output_tokens", sa.Integer(), nullable=True),
        sa.Column("actual_output_tokens", sa.Integer(), nullable=True),
        sa.Column("prompt_size_bytes", sa.Integer(), nullable=True),
        sa.Column("completion_truncated", sa.Boolean(), nullable=True),
    ]

    for column in token_columns:
        _add_column_if_missing("pipeline_executions", column.copy())
        _add_column_if_missing("stage_executions", column.copy())
        _add_column_if_missing("prompt_observability_logs", column.copy())


def downgrade() -> None:
    # Intentionally no-op for additive observability safety.
    pass
