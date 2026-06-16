"""add agent_memories table

Revision ID: 039_add_agent_memories_table
Revises: 038_add_retrieval_logs_graph
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "039_add_agent_memories_table"
down_revision = "038_add_retrieval_logs_graph"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_memories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("database_id", sa.Integer(), sa.ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("context_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("memory_type", sa.String(length=128), nullable=False, server_default=sa.text("'query_history'")),
        sa.Column("tags_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
        sa.Column("vector_id", sa.String(length=255), nullable=True),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agent_memories_database_id", "agent_memories", ["database_id"])
    op.create_index("ix_agent_memories_memory_type", "agent_memories", ["memory_type"])
    op.create_index("ix_agent_memories_vector_id", "agent_memories", ["vector_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_memories_vector_id", table_name="agent_memories")
    op.drop_index("ix_agent_memories_memory_type", table_name="agent_memories")
    op.drop_index("ix_agent_memories_database_id", table_name="agent_memories")
    op.drop_table("agent_memories")
