"""Create governance_packages table for canonical governance intelligence.

Revision ID: 021_create_governance_packages
Revises: 020_add_semantic_business
Create Date: 2026-06-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "021_create_governance_packages"
down_revision = "020_add_semantic_business"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "governance_packages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("database_id", sa.Integer(), sa.ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("table_id", sa.Integer(), sa.ForeignKey("database_tables.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("table_name", sa.String(length=255), nullable=False),
        sa.Column("schema_name", sa.String(length=255), nullable=False),
        sa.Column("table_summary", sa.Text(), nullable=True),
        sa.Column("business_purpose", sa.Text(), nullable=True),
        sa.Column("pii_columns", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("risk_columns", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("sensitive_columns", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("overall_risk", sa.String(length=32), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("prompt_id", sa.String(length=255), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("raw_failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_governance_packages_database_id", "governance_packages", ["database_id"])
    op.create_index("ix_governance_packages_table_id", "governance_packages", ["table_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_governance_packages_table_id", table_name="governance_packages")
    op.drop_index("ix_governance_packages_database_id", table_name="governance_packages")
    op.drop_table("governance_packages")
