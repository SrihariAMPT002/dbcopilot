"""add prompt embeddings and dashboard prompt metrics

Revision ID: 034_add_prompt_embeddings
Revises: 033_add_prompt_packages
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "034_add_prompt_embeddings"
down_revision = "033_add_prompt_packages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prompt_embeddings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("prompt_package_id", sa.Integer(), sa.ForeignKey("prompt_packages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
        sa.Column("vector", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_prompt_embeddings_prompt_package_id", "prompt_embeddings", ["prompt_package_id"])


def downgrade() -> None:
    op.drop_index("ix_prompt_embeddings_prompt_package_id", table_name="prompt_embeddings")
    op.drop_table("prompt_embeddings")

