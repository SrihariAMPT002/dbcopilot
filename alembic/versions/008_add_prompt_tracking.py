"""Add prompt tracking fields to readiness snapshots.

Revision ID: 007_add_prompt_tracking
Revises: 006_add_readiness_scores
Create Date: 2026-06-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "007_add_prompt_tracking"
down_revision = "006_add_readiness_scores"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "readiness_snapshots",
        sa.Column("prompt_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "readiness_snapshots",
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "readiness_snapshots",
        sa.Column("model_name", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("readiness_snapshots", "model_name")
    op.drop_column("readiness_snapshots", "prompt_version")
    op.drop_column("readiness_snapshots", "prompt_id")
