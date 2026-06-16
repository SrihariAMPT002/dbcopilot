"""add embedding_documents table

Revision ID: 035_add_embedding_documents
Revises: 034_add_prompt_embeddings
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "035_add_embedding_documents"
down_revision = "034_add_prompt_embeddings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "embedding_documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("database_id", sa.Integer(), sa.ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_type", sa.String(length=128), nullable=False),
        sa.Column("source_package", sa.String(length=128), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
        sa.Column("vector_id", sa.String(length=255), nullable=True),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_embedding_documents_database_id", "embedding_documents", ["database_id"])
    op.create_index("ix_embedding_documents_document_type", "embedding_documents", ["document_type"])
    op.create_index("ix_embedding_documents_vector_id", "embedding_documents", ["vector_id"])


def downgrade() -> None:
    op.drop_index("ix_embedding_documents_vector_id", table_name="embedding_documents")
    op.drop_index("ix_embedding_documents_document_type", table_name="embedding_documents")
    op.drop_index("ix_embedding_documents_database_id", table_name="embedding_documents")
    op.drop_table("embedding_documents")

