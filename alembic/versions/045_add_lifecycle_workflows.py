"""add database lifecycle workflows

Revision ID: 045_add_lifecycle_workflows
Revises: 044_add_kpi_execution_fields
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "045_add_lifecycle_workflows"
down_revision = "044_add_kpi_execution_fields"
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns(table_name)}
    if column.name not in columns:
        op.add_column(table_name, column)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "database_lifecycle_events" not in tables:
        op.create_table(
            "database_lifecycle_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "connected_db_id",
                sa.Integer(),
                sa.ForeignKey("connected_databases.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("actor", sa.String(length=255), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("trace_id", sa.String(length=255), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_database_lifecycle_events_connected_db_id", "database_lifecycle_events", ["connected_db_id"])
        op.create_index("ix_database_lifecycle_events_event_type", "database_lifecycle_events", ["event_type"])
        op.create_index("ix_database_lifecycle_events_trace_id", "database_lifecycle_events", ["trace_id"])

    enum_name = "database_lifecycle_status_enum"
    if enum_name not in {enum["name"] for enum in inspector.get_enums()}:
        op.execute(
            "DO $$ BEGIN "
            "CREATE TYPE database_lifecycle_status_enum AS ENUM ('ACTIVE', 'DISCONNECTED', 'ARCHIVED', 'DELETED'); "
            "EXCEPTION WHEN duplicate_object THEN null; END $$;"
        )

    _add_column_if_missing(
        "connected_databases",
        sa.Column(
            "lifecycle_status",
            sa.Enum("ACTIVE", "DISCONNECTED", "ARCHIVED", "DELETED", name=enum_name),
            nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),
    )
    _add_column_if_missing("connected_databases", sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing("connected_databases", sa.Column("disconnected_by", sa.String(length=255), nullable=True))
    _add_column_if_missing("connected_databases", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing("connected_databases", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing("connected_databases", sa.Column("deletion_summary", sa.Text(), nullable=True))

    op.execute("UPDATE connected_databases SET lifecycle_status = 'ACTIVE' WHERE lifecycle_status IS NULL")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("connected_databases")}
    for name in [
        "deletion_summary",
        "deleted_at",
        "archived_at",
        "disconnected_by",
        "disconnected_at",
        "lifecycle_status",
    ]:
        if name in columns:
            op.drop_column("connected_databases", name)

    tables = inspector.get_table_names()
    if "database_lifecycle_events" in tables:
        op.drop_index("ix_database_lifecycle_events_trace_id", table_name="database_lifecycle_events")
        op.drop_index("ix_database_lifecycle_events_event_type", table_name="database_lifecycle_events")
        op.drop_index("ix_database_lifecycle_events_connected_db_id", table_name="database_lifecycle_events")
        op.drop_table("database_lifecycle_events")
    op.execute("DROP TYPE IF EXISTS database_lifecycle_status_enum")
