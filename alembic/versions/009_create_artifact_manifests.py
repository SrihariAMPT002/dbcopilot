"""Create artifact_manifests table.

Revision ID: 009_create_artifact_manifests
Revises: 008_add_prompt_tracking
Create Date: 2026-06-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "009_create_artifact_manifests"
down_revision = "008_add_prompt_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    artifact_type_enum = sa.Enum(
        "semantic_summary.json",
        "embeddings.json",
        "relationship_graph.json",
        "prompt_context.md",
        "database_context.md",
        "system_prompt.md",
        "rag_context.md",
        "agent_context.json",
        "text_to_sql_context.md",
        name="artifact_type_enum",
    )
    export_status_enum = sa.Enum(
        "QUEUED",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        name="artifact_export_status_enum",
    )

    op.create_table(
        "artifact_manifests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("database_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", artifact_type_enum, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("schema_hash", sa.String(length=128), nullable=False),
        sa.Column("export_status", export_status_enum, nullable=False, server_default="QUEUED"),
        sa.Column("artifact_path", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["database_id"], ["connected_databases.id"], ondelete="CASCADE"),
    )

    op.create_index("ix_artifact_manifests_database_id", "artifact_manifests", ["database_id"])
    op.create_index("ix_artifact_manifests_artifact_type", "artifact_manifests", ["artifact_type"])
    op.create_index("ix_artifact_manifests_schema_hash", "artifact_manifests", ["schema_hash"])
    op.create_index("ix_artifact_manifests_export_status", "artifact_manifests", ["export_status"])
    op.create_index("ix_artifact_manifests_generated_at", "artifact_manifests", ["generated_at"])


def downgrade() -> None:
    op.drop_index("ix_artifact_manifests_generated_at", table_name="artifact_manifests")
    op.drop_index("ix_artifact_manifests_export_status", table_name="artifact_manifests")
    op.drop_index("ix_artifact_manifests_schema_hash", table_name="artifact_manifests")
    op.drop_index("ix_artifact_manifests_artifact_type", table_name="artifact_manifests")
    op.drop_index("ix_artifact_manifests_database_id", table_name="artifact_manifests")
    op.drop_table("artifact_manifests")
    op.execute("DROP TYPE IF EXISTS artifact_export_status_enum")
    op.execute("DROP TYPE IF EXISTS artifact_type_enum")
