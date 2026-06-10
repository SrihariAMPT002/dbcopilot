"""Add overall_score to readiness_snapshots.

Revision ID: 012_add_overall_score
Revises: 011_add_column_tracking
Create Date: 2026-06-09 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "012_add_overall_score"
down_revision = "011_add_column_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    columns = {
        column["name"]
        for column in inspector.get_columns("readiness_snapshots")
    }

    if "overall_score" not in columns:
        op.add_column(
            "readiness_snapshots",
            sa.Column(
                "overall_score",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    columns = {
        column["name"]
        for column in inspector.get_columns("readiness_snapshots")
    }

    if "overall_score" in columns:
        op.drop_column("readiness_snapshots", "overall_score")