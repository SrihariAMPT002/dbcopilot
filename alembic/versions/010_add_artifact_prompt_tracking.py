"""Add prompt tracking fields to artifact_manifests.

Revision ID: 010_add_artifact_prompt_tracking
Revises: 009_create_artifact_manifests
Create Date: 2026-06-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "010_add_artifact_prompt_tracking"
down_revision = "009_create_artifact_manifests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "artifact_manifests",
        sa.Column("prompt_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "artifact_manifests",
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "artifact_manifests",
        sa.Column("model_name", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("artifact_manifests", "model_name")
    op.drop_column("artifact_manifests", "prompt_version")
    op.drop_column("artifact_manifests", "prompt_id")
