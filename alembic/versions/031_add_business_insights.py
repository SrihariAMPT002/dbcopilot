"""Add business insights table.

Revision ID: 031_add_business_insights
Revises: 030_add_business_events_table
Create Date: 2026-06-15 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "031_add_business_insights"
down_revision = "030_add_business_events_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "business_insights",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("database_id", sa.Integer(), sa.ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("insight_text", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("impact_level", sa.String(length=32), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_business_insights_database_id"), "business_insights", ["database_id"])
    op.create_index(op.f("ix_business_insights_confidence_score"), "business_insights", ["confidence_score"])


def downgrade() -> None:
    op.drop_index(op.f("ix_business_insights_confidence_score"), table_name="business_insights")
    op.drop_index(op.f("ix_business_insights_database_id"), table_name="business_insights")
    op.drop_table("business_insights")
