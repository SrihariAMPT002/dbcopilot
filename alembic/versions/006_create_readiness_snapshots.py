"""Create readiness_snapshots table.

Revision ID: 006_create_readiness_snapshots
Revises: 005_add_column_semantics
Create Date: 2026-06-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "006_create_readiness_snapshots"
down_revision = "005_add_column_semantics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    readiness_status_enum = sa.Enum(
        "NOT_READY",
        "PARTIAL",
        "READY",
        "STALE",
        name="readiness_status_enum",
    )

    op.create_table(
        "readiness_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("database_id", sa.Integer(), nullable=False),
        sa.Column("metadata_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("semantic_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embeddings_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("relationship_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prompt_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("readiness_status", readiness_status_enum, nullable=False, server_default="NOT_READY"),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["database_id"], ["connected_databases.id"], ondelete="CASCADE"),
    )

    op.create_index("ix_readiness_snapshots_database_id", "readiness_snapshots", ["database_id"])
    op.create_index("ix_readiness_snapshots_readiness_status", "readiness_snapshots", ["readiness_status"])
    op.create_index("ix_readiness_snapshots_generated_at", "readiness_snapshots", ["generated_at"])


def downgrade() -> None:
    op.drop_index("ix_readiness_snapshots_generated_at", table_name="readiness_snapshots")
    op.drop_index("ix_readiness_snapshots_readiness_status", table_name="readiness_snapshots")
    op.drop_index("ix_readiness_snapshots_database_id", table_name="readiness_snapshots")
    op.drop_table("readiness_snapshots")
    op.execute("DROP TYPE IF EXISTS readiness_status_enum")
