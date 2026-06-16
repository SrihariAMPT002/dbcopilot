"""placeholder graph retrieval migration

Revision ID: 038_add_retrieval_logs_graph
Revises: 037_add_retrieval_logs_table
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op


revision = "038_add_retrieval_logs_graph"
down_revision = "037_add_retrieval_logs_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

