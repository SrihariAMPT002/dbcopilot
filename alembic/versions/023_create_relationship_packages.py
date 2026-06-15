"""Create relationship packages and telemetry tables.

Revision ID: 023_create_relationship_packages
Revises: 022_create_semantic_packages
Create Date: 2026-06-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "023_create_relationship_packages"
down_revision = "022_create_semantic_packages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "relationship_packages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("database_id", sa.Integer(), sa.ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cluster_id", sa.String(length=128), nullable=False),
        sa.Column("domain_name", sa.String(length=255), nullable=True),
        sa.Column("cluster_summary", sa.Text(), nullable=True),
        sa.Column("entity_graph", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("business_process_flows", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("hidden_relationships", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("upstream_dependencies", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("downstream_dependencies", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("lifecycle_flows", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("prompt_id", sa.String(length=255), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_relationship_packages_database_id", "relationship_packages", ["database_id"])
    op.create_index("ix_relationship_packages_cluster_id", "relationship_packages", ["cluster_id"])

    op.create_table(
        "relationship_cluster_telemetry",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("database_id", sa.Integer(), sa.ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cluster_id", sa.String(length=128), nullable=False),
        sa.Column("domain_name", sa.String(length=255), nullable=True),
        sa.Column("cluster_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("relationship_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actual_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actual_output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prompt_truncated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("finish_reason", sa.String(length=64), nullable=True),
        sa.Column("response_quality", sa.String(length=64), nullable=True),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("prompt_id", sa.String(length=255), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_relationship_cluster_telemetry_database_id", "relationship_cluster_telemetry", ["database_id"])
    op.create_index("ix_relationship_cluster_telemetry_cluster_id", "relationship_cluster_telemetry", ["cluster_id"])


def downgrade() -> None:
    op.drop_index("ix_relationship_cluster_telemetry_cluster_id", table_name="relationship_cluster_telemetry")
    op.drop_index("ix_relationship_cluster_telemetry_database_id", table_name="relationship_cluster_telemetry")
    op.drop_table("relationship_cluster_telemetry")
    op.drop_index("ix_relationship_packages_cluster_id", table_name="relationship_packages")
    op.drop_index("ix_relationship_packages_database_id", table_name="relationship_packages")
    op.drop_table("relationship_packages")
