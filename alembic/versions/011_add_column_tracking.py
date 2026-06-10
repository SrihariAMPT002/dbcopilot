"""Add prompt tracking and metadata fingerprint to column_semantics.

Revision ID: 011_add_column_tracking
Revises: 010_add_artifact_prompt_tracking
Create Date: 2026-06-08 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "011_add_column_tracking"
down_revision = "010_add_artifact_prompt_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "column_semantics",
        sa.Column("prompt_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "column_semantics",
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "column_semantics",
        sa.Column("model_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "column_semantics",
        sa.Column("metadata_fingerprint", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("column_semantics", "metadata_fingerprint")
    op.drop_column("column_semantics", "model_name")
    op.drop_column("column_semantics", "prompt_version")
    op.drop_column("column_semantics", "prompt_id")
