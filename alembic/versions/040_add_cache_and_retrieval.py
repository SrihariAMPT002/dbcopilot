"""add semantic_cache and retrieval_evaluations tables

Revision ID: 040_add_cache_and_retrieval
Revises: 039_add_agent_memories_table
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "040_add_cache_and_retrieval"
down_revision = "039_add_agent_memories_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "semantic_cache",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("database_id", sa.Integer(), nullable=False),
        sa.Column("query_hash", sa.String(length=255), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=True),
        sa.Column("ttl_seconds", sa.Integer(), nullable=False, server_default=sa.text("3600")),
        sa.Column("last_used", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_semantic_cache_database_id", "semantic_cache", ["database_id"])
    op.create_index("ix_semantic_cache_query_hash", "semantic_cache", ["query_hash"], unique=True)

    op.create_table(
        "retrieval_evaluations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("database_id", sa.Integer(), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("precision_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("recall_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("mrr_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("ndcg_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("coverage_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("hallucination_risk", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_retrieval_evaluations_database_id", "retrieval_evaluations", ["database_id"])


def downgrade() -> None:
    op.drop_index("ix_retrieval_evaluations_database_id", table_name="retrieval_evaluations")
    op.drop_table("retrieval_evaluations")
    op.drop_index("ix_semantic_cache_query_hash", table_name="semantic_cache")
    op.drop_index("ix_semantic_cache_database_id", table_name="semantic_cache")
    op.drop_table("semantic_cache")
