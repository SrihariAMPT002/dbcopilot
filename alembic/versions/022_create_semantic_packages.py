"""Create semantic_packages and table_semantic_packages tables.

Revision ID: 022_create_semantic_packages
Revises: 021_create_governance_packages
Create Date: 2026-06-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "022_create_semantic_packages"
down_revision = "021_create_governance_packages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "semantic_packages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("database_id", sa.Integer(), sa.ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("business_domain", sa.Text(), nullable=True),
        sa.Column("semantic_summary", sa.Text(), nullable=True),
        sa.Column("business_entities", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("business_processes", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("business_capabilities", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("business_glossary", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("prompt_id", sa.String(length=255), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_semantic_packages_database_id", "semantic_packages", ["database_id"])

    op.create_table(
        "table_semantic_packages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("database_id", sa.Integer(), sa.ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("table_id", sa.Integer(), sa.ForeignKey("database_tables.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("business_purpose", sa.Text(), nullable=True),
        sa.Column("business_entity", sa.Text(), nullable=True),
        sa.Column("business_capability", sa.Text(), nullable=True),
        sa.Column("business_process", sa.Text(), nullable=True),
        sa.Column("business_keywords", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("semantic_summary", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("prompt_id", sa.String(length=255), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_table_semantic_packages_database_id", "table_semantic_packages", ["database_id"])
    op.create_index("ix_table_semantic_packages_table_id", "table_semantic_packages", ["table_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_table_semantic_packages_table_id", table_name="table_semantic_packages")
    op.drop_index("ix_table_semantic_packages_database_id", table_name="table_semantic_packages")
    op.drop_table("table_semantic_packages")
    op.drop_index("ix_semantic_packages_database_id", table_name="semantic_packages")
    op.drop_table("semantic_packages")
