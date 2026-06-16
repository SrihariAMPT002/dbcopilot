"""add missing KPI cluster fields

Revision ID: 043_add_kpi_cluster_fields
Revises: 042_create_pipeline_execution
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "043_add_kpi_cluster_fields"
down_revision = "042_create_pipeline_execution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("kpi_intelligence")}

    if "cluster_id" not in columns:
        op.add_column("kpi_intelligence", sa.Column("cluster_id", sa.String(length=128), nullable=True))
        op.create_index("ix_kpi_intelligence_cluster_id", "kpi_intelligence", ["cluster_id"])

    if "cluster_name" not in columns:
        op.add_column("kpi_intelligence", sa.Column("cluster_name", sa.String(length=255), nullable=True))

    if "cluster_size" not in columns:
        op.add_column("kpi_intelligence", sa.Column("cluster_size", sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("kpi_intelligence")}

    if "cluster_size" in columns:
        op.drop_column("kpi_intelligence", "cluster_size")

    if "cluster_name" in columns:
        op.drop_column("kpi_intelligence", "cluster_name")

    if "cluster_id" in columns:
        op.drop_index("ix_kpi_intelligence_cluster_id", table_name="kpi_intelligence")
        op.drop_column("kpi_intelligence", "cluster_id")
