"""add vector_collections table

Revision ID: 036_add_vector_collections
Revises: 035_add_embedding_documents
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "036_add_vector_collections"
down_revision = "035_add_embedding_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vector_collections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("collection_name", sa.String(length=255), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
        sa.Column("vector_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(length=64), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("last_synced", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_vector_collections_collection_name", "vector_collections", ["collection_name"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_vector_collections_collection_name", table_name="vector_collections")
    op.drop_table("vector_collections")

