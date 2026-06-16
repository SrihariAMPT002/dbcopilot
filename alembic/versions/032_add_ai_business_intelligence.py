"""add ai business intelligence package tables

Revision ID: 032_add_ai_business_intelligence
Revises: 031_add_business_insights
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "032_add_ai_business_intelligence"
down_revision = "031_add_business_insights"
branch_labels = None
depends_on = None


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str], **kwargs) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {idx["name"] for idx in inspector.get_indexes(table_name)}
    if index_name not in existing:
        op.create_index(index_name, table_name, columns, **kwargs)


def upgrade() -> None:
    op.create_table(
        "opportunity_recommendations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("database_id", sa.Integer(), sa.ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recommendation_text", sa.Text(), nullable=False),
        sa.Column("recommendation_type", sa.String(length=128), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("evidence", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    _create_index_if_missing("ix_opportunity_recommendations_database_id", "opportunity_recommendations", ["database_id"])

    op.create_table(
        "data_products",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("database_id", sa.Integer(), sa.ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("product_type", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("evidence", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    _create_index_if_missing("ix_data_products_database_id", "data_products", ["database_id"])

    op.create_table(
        "warehouse_designs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("database_id", sa.Integer(), sa.ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("design_name", sa.String(length=255), nullable=False),
        sa.Column("design_type", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("evidence", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    _create_index_if_missing("ix_warehouse_designs_database_id", "warehouse_designs", ["database_id"])

    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("database_id", sa.Integer(), sa.ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recommendation_text", sa.Text(), nullable=False),
        sa.Column("recommendation_type", sa.String(length=128), nullable=True),
        sa.Column("priority", sa.String(length=32), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("evidence", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    _create_index_if_missing("ix_recommendations_database_id", "recommendations", ["database_id"])

    op.create_table(
        "predictive_readiness",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("database_id", sa.Integer(), sa.ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_readiness_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("text_to_sql_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rag_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("analytics_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("forecasting_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("anomaly_detection_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ml_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("agent_capabilities", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("evidence", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    _create_index_if_missing("ix_predictive_readiness_database_id", "predictive_readiness", ["database_id"])

    op.create_table(
        "agent_capabilities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("database_id", sa.Integer(), sa.ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("capability_name", sa.String(length=255), nullable=False),
        sa.Column("capability_type", sa.String(length=128), nullable=True),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("evidence", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    _create_index_if_missing("ix_agent_capabilities_database_id", "agent_capabilities", ["database_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_capabilities_database_id", table_name="agent_capabilities")
    op.drop_table("agent_capabilities")
    op.drop_index("ix_predictive_readiness_database_id", table_name="predictive_readiness")
    op.drop_table("predictive_readiness")
    op.drop_index("ix_recommendations_database_id", table_name="recommendations")
    op.drop_table("recommendations")
    op.drop_index("ix_warehouse_designs_database_id", table_name="warehouse_designs")
    op.drop_table("warehouse_designs")
    op.drop_index("ix_data_products_database_id", table_name="data_products")
    op.drop_table("data_products")
    op.drop_index("ix_opportunity_recommendations_database_id", table_name="opportunity_recommendations")
    op.drop_table("opportunity_recommendations")
