"""Add business events table.

Revision ID: 030_add_business_events_table
Revises: 029_add_kpi_packages_table
Create Date: 2026-06-15 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "030_add_business_events_table"
down_revision = "029_add_kpi_packages_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "business_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("database_id", sa.Integer(), sa.ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_name", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=True),
        sa.Column("source_tables", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_business_events_database_id"), "business_events", ["database_id"])
    op.create_index(op.f("ix_business_events_event_name"), "business_events", ["event_name"])


def downgrade() -> None:
    op.drop_index(op.f("ix_business_events_event_name"), table_name="business_events")
    op.drop_index(op.f("ix_business_events_database_id"), table_name="business_events")
    op.drop_table("business_events")
