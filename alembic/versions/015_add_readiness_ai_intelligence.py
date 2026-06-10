"""Add AI readiness intelligence fields.

Migration hygiene note:
- Historical duplicate numbering patterns exist in 006_* and 008_* migrations.
- Revision IDs remain unique and chained correctly; do not renumber old revisions.

Revision ID: 013_add_readiness_ai_intelligence
Revises: 012_add_kpi_intelligence
Create Date: 2026-06-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "013_add_readiness_ai_intelligence"
down_revision = "012_add_kpi_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    readiness_columns = {column["name"] for column in inspector.get_columns("readiness_snapshots")}

    additions = [
        ("ai_summary", sa.Text(), None),
        ("ai_recommendations", sa.Text(), None),
        ("ai_risks", sa.Text(), None),
        ("ai_roadmap", sa.Text(), None),
        ("ai_confidence", sa.Float(), "0"),
    ]
    for name, col_type, default in additions:
        if name not in readiness_columns:
            op.add_column(
                "readiness_snapshots",
                sa.Column(name, col_type, nullable=(name != "ai_confidence"), server_default=default),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    readiness_columns = {column["name"] for column in inspector.get_columns("readiness_snapshots")}
    for name in ["ai_confidence", "ai_roadmap", "ai_risks", "ai_recommendations", "ai_summary"]:
        if name in readiness_columns:
            op.drop_column("readiness_snapshots", name)
