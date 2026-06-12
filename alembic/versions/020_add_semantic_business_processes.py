"""Add business_processes fields for V3 semantic intelligence.

Revision ID: 020_add_semantic_business_processes
Revises: 019_add_governance_intelligence_fields
Create Date: 2026-06-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "020_add_semantic_business_processes"
down_revision = "019_add_governance_intelligence_fields"
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {item["name"] for item in inspector.get_columns(table_name)}
    if column.name not in existing:
        op.add_column(table_name, column)


def upgrade() -> None:
    _add_column_if_missing("database_semantics", sa.Column("business_processes", sa.Text(), nullable=False, server_default="[]"))
    _add_column_if_missing("schema_semantics", sa.Column("business_processes", sa.Text(), nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("schema_semantics", "business_processes")
    op.drop_column("database_semantics", "business_processes")
