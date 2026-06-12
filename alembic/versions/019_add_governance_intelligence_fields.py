"""Add governance intelligence fields to column_semantics.

Revision ID: 019_add_governance_intelligence_fields
Revises: 018_add_subcluster_fields
Create Date: 2026-06-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "019_add_governance_intelligence_fields"
down_revision = "018_add_subcluster_fields"
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {item["name"] for item in inspector.get_columns(table_name)}
    if column.name not in existing:
        op.add_column(table_name, column)


def upgrade() -> None:
    _add_column_if_missing("column_semantics", sa.Column("business_meaning", sa.Text(), nullable=True))
    _add_column_if_missing("column_semantics", sa.Column("governance_reasoning", sa.Text(), nullable=True))
    _add_column_if_missing("column_semantics", sa.Column("table_purpose", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("column_semantics", "table_purpose")
    op.drop_column("column_semantics", "governance_reasoning")
    op.drop_column("column_semantics", "business_meaning")
