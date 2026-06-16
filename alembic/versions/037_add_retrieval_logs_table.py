"""add retrieval_logs table

Revision ID: 037_add_retrieval_logs_table
Revises: 036_add_vector_collections
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "037_add_retrieval_logs_table"
down_revision = "036_add_vector_collections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "retrieval_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("retrieved_documents", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("reranked_documents", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("scores", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("retrieval_logs")

