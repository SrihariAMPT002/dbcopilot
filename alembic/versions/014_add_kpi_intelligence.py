"""Add KPI intelligence tables and readiness snapshot fields.

Revision ID: 014_add_kpi_intelligence
Revises: 013_add_relationship_columns
Create Date: 2026-06-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "014_add_kpi_intelligence"
down_revision = "013_add_relationship_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    pipeline_job_types = {enum.get("name") for enum in inspector.get_enums()} if hasattr(inspector, "get_enums") else set()
    if "pipeline_job_type_enum" in pipeline_job_types:
        op.execute("ALTER TYPE pipeline_job_type_enum ADD VALUE IF NOT EXISTS 'KPI_INTELLIGENCE'")

    op.create_table(
        "kpi_intelligence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("database_id", sa.Integer(), nullable=False),
        sa.Column("prompt_id", sa.String(length=255), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("business_meaning", sa.Text(), nullable=True),
        sa.Column("formula", sa.Text(), nullable=True),
        sa.Column("source_tables", sa.Text(), nullable=True),
        sa.Column("source_columns", sa.Text(), nullable=True),
        sa.Column("dimensions", sa.Text(), nullable=True),
        sa.Column("filters", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column("lineage_summary", sa.Text(), nullable=True),
        sa.Column("discovery_source", sa.String(length=255), nullable=True),
        sa.Column("package_version", sa.String(length=64), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("metadata_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="discovered"),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["database_id"], ["connected_databases.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_kpi_intelligence_database_id", "kpi_intelligence", ["database_id"])
    op.create_index("ix_kpi_intelligence_name", "kpi_intelligence", ["name"])
    op.create_index("ix_kpi_intelligence_prompt_id", "kpi_intelligence", ["prompt_id"])
    op.create_index("ix_kpi_intelligence_metadata_fingerprint", "kpi_intelligence", ["metadata_fingerprint"])
    op.create_index("ix_kpi_intelligence_status", "kpi_intelligence", ["status"])

    op.create_table(
        "kpi_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("database_id", sa.Integer(), nullable=False),
        sa.Column("prompt_id", sa.String(length=255), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("artifact_type", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("schema_hash", sa.String(length=128), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("metadata_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("artifact_path", sa.Text(), nullable=False),
        sa.Column("mime", sa.String(length=128), nullable=False, server_default="application/json"),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["database_id"], ["connected_databases.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_kpi_artifacts_database_id", "kpi_artifacts", ["database_id"])
    op.create_index("ix_kpi_artifacts_artifact_type", "kpi_artifacts", ["artifact_type"])
    op.create_index("ix_kpi_artifacts_prompt_id", "kpi_artifacts", ["prompt_id"])
    op.create_index("ix_kpi_artifacts_schema_hash", "kpi_artifacts", ["schema_hash"])
    op.create_index("ix_kpi_artifacts_metadata_fingerprint", "kpi_artifacts", ["metadata_fingerprint"])

    readiness_columns = {
        column["name"]
        for column in inspector.get_columns("readiness_snapshots")
    }
    if "kpi_score" not in readiness_columns:
        op.add_column("readiness_snapshots", sa.Column("kpi_score", sa.Integer(), nullable=False, server_default="0"))
    if "kpi_readiness_score" not in readiness_columns:
        op.add_column("readiness_snapshots", sa.Column("kpi_readiness_score", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    readiness_columns = {column["name"] for column in inspector.get_columns("readiness_snapshots")}
    if "kpi_readiness_score" in readiness_columns:
        op.drop_column("readiness_snapshots", "kpi_readiness_score")
    if "kpi_score" in readiness_columns:
        op.drop_column("readiness_snapshots", "kpi_score")

    op.drop_index("ix_kpi_artifacts_metadata_fingerprint", table_name="kpi_artifacts")
    op.drop_index("ix_kpi_artifacts_schema_hash", table_name="kpi_artifacts")
    op.drop_index("ix_kpi_artifacts_prompt_id", table_name="kpi_artifacts")
    op.drop_index("ix_kpi_artifacts_artifact_type", table_name="kpi_artifacts")
    op.drop_index("ix_kpi_artifacts_database_id", table_name="kpi_artifacts")
    op.drop_table("kpi_artifacts")

    op.drop_index("ix_kpi_intelligence_status", table_name="kpi_intelligence")
    op.drop_index("ix_kpi_intelligence_metadata_fingerprint", table_name="kpi_intelligence")
    op.drop_index("ix_kpi_intelligence_prompt_id", table_name="kpi_intelligence")
    op.drop_index("ix_kpi_intelligence_name", table_name="kpi_intelligence")
    op.drop_index("ix_kpi_intelligence_database_id", table_name="kpi_intelligence")
    op.drop_table("kpi_intelligence")
