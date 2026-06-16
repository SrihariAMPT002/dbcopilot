"""Add KPI packages table.

Revision ID: 029_add_kpi_packages_table
Revises: 028_add_relationship_scores
Create Date: 2026-06-15 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "029_add_kpi_packages_table"
down_revision = "028_add_relationship_scores"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kpi_packages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("database_id", sa.Integer(), sa.ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kpi_name", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("formula", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=255), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_kpi_packages_database_id"), "kpi_packages", ["database_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_kpi_packages_database_id"), table_name="kpi_packages")
    op.drop_table("kpi_packages")
