"""Add stage blocking provenance to stage executions.

Revision ID: 050_add_stage_provenance
Revises: 049_add_pipeline_provenance
Create Date: 2026-06-17
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "050_add_stage_provenance"
down_revision = "049_add_pipeline_provenance"
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
    _add_column_if_missing("stage_executions", sa.Column("blocked_by_stage", sa.String(length=64), nullable=True))


def downgrade() -> None:
    pass
