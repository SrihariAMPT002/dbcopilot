"""add missing KPI execution fields

Revision ID: 044_add_kpi_execution_fields
Revises: 043_add_kpi_cluster_fields
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "044_add_kpi_execution_fields"
down_revision = "043_add_kpi_cluster_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("kpi_intelligence")}

    field_specs = [
        ("estimated_tokens", sa.Integer()),
        ("actual_input_tokens", sa.Integer()),
        ("actual_output_tokens", sa.Integer()),
        ("execution_status", sa.String(length=64)),
        ("used_fallback", sa.Boolean()),
        ("retry_count", sa.Integer()),
    ]

    for name, column_type in field_specs:
        if name in columns:
            continue
        if name == "used_fallback":
            op.add_column("kpi_intelligence", sa.Column(name, column_type, nullable=False, server_default=sa.false()))
            continue
        if name == "retry_count":
            op.add_column("kpi_intelligence", sa.Column(name, column_type, nullable=False, server_default="0"))
            continue
        op.add_column("kpi_intelligence", sa.Column(name, column_type, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("kpi_intelligence")}

    for name in [
        "retry_count",
        "used_fallback",
        "execution_status",
        "actual_output_tokens",
        "actual_input_tokens",
        "estimated_tokens",
    ]:
        if name in columns:
            op.drop_column("kpi_intelligence", name)
