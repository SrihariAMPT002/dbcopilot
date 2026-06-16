"""add prompt studio packages and observability tables

Revision ID: 033_add_prompt_packages
Revises: 032_add_ai_business_intelligence
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "033_add_prompt_packages"
down_revision = "032_add_ai_business_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prompt_packages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("database_id", sa.Integer(), sa.ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_type", sa.String(length=128), nullable=False),
        sa.Column("template_id", sa.String(length=255), nullable=True),
        sa.Column("generated_prompt", sa.Text(), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("generation_metadata", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("execution_status", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_prompt_packages_database_id", "prompt_packages", ["database_id"])
    op.create_index("ix_prompt_packages_artifact_type", "prompt_packages", ["artifact_type"])

    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("prompt_package_id", sa.Integer(), sa.ForeignKey("prompt_packages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("generated_prompt", sa.Text(), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("template_id", sa.String(length=255), nullable=True),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_prompt_versions_prompt_package_id", "prompt_versions", ["prompt_package_id"])

    op.create_table(
        "prompt_observability_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("prompt_package_id", sa.Integer(), sa.ForeignKey("prompt_packages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("finish_reason", sa.String(length=64), nullable=True),
        sa.Column("execution_status", sa.String(length=64), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_prompt_observability_logs_prompt_package_id", "prompt_observability_logs", ["prompt_package_id"])

    op.create_table(
        "prompt_evaluations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("prompt_package_id", sa.Integer(), sa.ForeignKey("prompt_packages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("completeness_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("safety_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("grounding_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("hallucination_risk", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("sql_safety_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("rag_quality_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("agent_quality_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("prompt_quality_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("reasoning_summary", sa.Text(), nullable=True),
        sa.Column("packages_used", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_prompt_evaluations_prompt_package_id", "prompt_evaluations", ["prompt_package_id"])


def downgrade() -> None:
    op.drop_index("ix_prompt_evaluations_prompt_package_id", table_name="prompt_evaluations")
    op.drop_table("prompt_evaluations")
    op.drop_index("ix_prompt_observability_logs_prompt_package_id", table_name="prompt_observability_logs")
    op.drop_table("prompt_observability_logs")
    op.drop_index("ix_prompt_versions_prompt_package_id", table_name="prompt_versions")
    op.drop_table("prompt_versions")
    op.drop_index("ix_prompt_packages_artifact_type", table_name="prompt_packages")
    op.drop_index("ix_prompt_packages_database_id", table_name="prompt_packages")
    op.drop_table("prompt_packages")

