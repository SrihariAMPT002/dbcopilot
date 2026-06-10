"""Add richer category scores to readiness snapshots.

Revision ID: 006_add_readiness_scores
Revises: 006_create_readiness_snapshots
Create Date: 2026-06-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "006_add_readiness_scores"
down_revision = "006_create_readiness_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "readiness_snapshots",
        sa.Column("metadata_readiness_score", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "readiness_snapshots",
        sa.Column("semantic_readiness_score", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "readiness_snapshots",
        sa.Column("relationship_readiness_score", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "readiness_snapshots",
        sa.Column("ai_context_readiness_score", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "readiness_snapshots",
        sa.Column("governance_readiness_score", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("readiness_snapshots", "governance_readiness_score")
    op.drop_column("readiness_snapshots", "ai_context_readiness_score")
    op.drop_column("readiness_snapshots", "relationship_readiness_score")
    op.drop_column("readiness_snapshots", "semantic_readiness_score")
    op.drop_column("readiness_snapshots", "metadata_readiness_score")
