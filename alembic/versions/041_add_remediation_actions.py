"""add remediation_actions table

Revision ID: 041_add_remediation_actions
Revises: 040_add_cache_and_retrieval
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "041_add_remediation_actions"
down_revision = "040_add_cache_and_retrieval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "remediation_actions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("readiness_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("database_id", sa.Integer(), nullable=False),
        sa.Column("issue", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("expected_impact", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(length=32), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["readiness_snapshot_id"], ["readiness_snapshots.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_remediation_actions_database_id", "remediation_actions", ["database_id"])
    op.create_index("ix_remediation_actions_readiness_snapshot_id", "remediation_actions", ["readiness_snapshot_id"])


def downgrade() -> None:
    op.drop_index("ix_remediation_actions_readiness_snapshot_id", table_name="remediation_actions")
    op.drop_index("ix_remediation_actions_database_id", table_name="remediation_actions")
    op.drop_table("remediation_actions")
