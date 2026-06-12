"""Add missing contract fields to column_semantics.

Revision ID: 017_add__semantics_fields
Revises: 016_add_ai_contract_trace
Create Date: 2026-06-11
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "017_add__semantics_fields"
down_revision = "016_add_ai_contract_trace"
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {item["name"] for item in inspector.get_columns(table_name)}
    if column.name not in existing:
        op.add_column(table_name, column)


def upgrade() -> None:
    _add_column_if_missing("column_semantics", sa.Column("classification_source", sa.String(length=64), nullable=True))
    _add_column_if_missing("column_semantics", sa.Column("execution_status", sa.String(length=64), nullable=True))
    _add_column_if_missing("column_semantics", sa.Column("used_fallback", sa.Boolean(), nullable=False, server_default=sa.false()))
    _add_column_if_missing("column_semantics", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
    _add_column_if_missing("column_semantics", sa.Column("error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("column_semantics", "error_message")
    op.drop_column("column_semantics", "retry_count")
    op.drop_column("column_semantics", "used_fallback")
    op.drop_column("column_semantics", "execution_status")
    op.drop_column("column_semantics", "classification_source")
