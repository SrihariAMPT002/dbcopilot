# """Create complete initial schema including embeddings, relationship graph, and SSL support.

# Revision ID: 001_complete_initial_schema
# Revises:
# Create Date: 2026-05-27 00:00:00.000000
# """

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "001_complete_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================
    # ENUMS
    # =========================
    connection_status_enum = sa.Enum(
        "active",
        "inactive",
        "error",
        "testing",
        name="connection_status_enum",
    )

    database_type_enum = sa.Enum(
        "postgresql",
        "mysql",
        "sqlserver",
        "mongodb",
        name="database_type_enum",
    )

    sync_status_enum = sa.Enum(
        "pending",
        "running",
        "success",
        "failed",
        name="sync_status_enum",
    )

    table_type_enum = sa.Enum(
        "table",
        "view",
        "materialized_view",
        "foreign_table",
        name="table_type_enum",
    )

    embedding_status_enum = sa.Enum(
        "pending",
        "running",
        "completed",
        "failed",
        name="embedding_status_enum",
    )

    # =========================
    # CONNECTED DATABASES
    # =========================
    op.create_table(
        "connected_databases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("db_type", database_type_enum, nullable=False),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("database_name", sa.String(255), nullable=False),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("encrypted_password", sa.Text(), nullable=False),
        sa.Column("ssl_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", connection_status_enum, nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_connected_databases_name", "connected_databases", ["name"])
    op.create_index("ix_connected_databases_db_type", "connected_databases", ["db_type"])
    op.create_index("ix_connected_databases_status", "connected_databases", ["status"])

    # =========================
    # DATABASE SCHEMAS
    # =========================
    op.create_table(
        "database_schemas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("connected_db_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["connected_db_id"], ["connected_databases.id"], ondelete="CASCADE"),
    )

    op.create_index(
        "ix_database_schemas_connected_db_id",
        "database_schemas",
        ["connected_db_id"],
    )

    # =========================
    # DATABASE TABLES
    # =========================
    op.create_table(
        "database_tables",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("schema_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("table_type", table_type_enum, nullable=False),
        sa.Column("row_count", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["schema_id"], ["database_schemas.id"], ondelete="CASCADE"),
    )

    op.create_index("ix_database_tables_schema_id", "database_tables", ["schema_id"])

    # =========================
    # DATABASE COLUMNS
    # =========================
    op.create_table(
        "database_columns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("table_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("data_type", sa.String(255), nullable=False),
        sa.Column("ordinal_position", sa.Integer(), nullable=True),
        sa.Column("is_nullable", sa.Boolean(), nullable=False),
        sa.Column("is_primary_key", sa.Boolean(), nullable=False),
        sa.Column("is_foreign_key", sa.Boolean(), nullable=False),
        sa.Column("is_unique", sa.Boolean(), nullable=False),
        sa.Column("is_indexed", sa.Boolean(), nullable=False),
        sa.Column("default_value", sa.Text(), nullable=True),
        sa.Column("max_length", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["table_id"], ["database_tables.id"], ondelete="CASCADE"),
    )

    op.create_index("ix_database_columns_table_id", "database_columns", ["table_id"])

    # =========================
    # DATABASE RELATIONSHIPS
    # =========================
    op.create_table(
        "database_relationships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("table_id", sa.Integer(), nullable=False),
        sa.Column("column_name", sa.String(255), nullable=False),
        sa.Column("referenced_table_id", sa.Integer(), nullable=True),
        sa.Column("referenced_schema", sa.String(255), nullable=True),
        sa.Column("referenced_table_name", sa.String(255), nullable=False),
        sa.Column("referenced_column_name", sa.String(255), nullable=False),
        sa.Column("constraint_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["table_id"], ["database_tables.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["referenced_table_id"], ["database_tables.id"], ondelete="SET NULL"),
    )

    op.create_index(
        "ix_database_relationships_table_id",
        "database_relationships",
        ["table_id"],
    )

    # =========================
    # SYNC LOGS
    # =========================
    op.create_table(
        "sync_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("connected_db_id", sa.Integer(), nullable=False),
        sa.Column("status", sync_status_enum, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("schemas_synced", sa.Integer(), nullable=False),
        sa.Column("tables_synced", sa.Integer(), nullable=False),
        sa.Column("columns_synced", sa.Integer(), nullable=False),
        sa.Column("relationships_synced", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_details", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["connected_db_id"], ["connected_databases.id"], ondelete="CASCADE"),
    )

    op.create_index("ix_sync_logs_connected_db_id", "sync_logs", ["connected_db_id"])
    op.create_index("ix_sync_logs_status", "sync_logs", ["status"])

    # =========================
    # SCHEMA SEMANTICS
    # =========================
    op.create_table(
        "schema_semantics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("database_id", sa.Integer(), nullable=False),
        sa.Column("table_id", sa.Integer(), nullable=False),
        sa.Column("semantic_summary", sa.Text(), nullable=False),
        sa.Column("likely_usage", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("important_columns", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("business_keywords", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("possible_questions", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["database_id"], ["connected_databases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["table_id"], ["database_tables.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("table_id"),
    )

    op.create_index("ix_schema_semantics_database_id", "schema_semantics", ["database_id"])
    op.create_index("ix_schema_semantics_table_id", "schema_semantics", ["table_id"])

    # =========================
    # SCHEMA EMBEDDINGS
    # =========================
    op.create_table(
        "schema_embeddings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("table_id", sa.Integer(), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("vector_id", sa.String(length=255), nullable=True),
        sa.Column("embedding_status", embedding_status_enum, nullable=False),
        sa.Column("embedded_text", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["table_id"], ["database_tables.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("table_id"),
    )

    op.create_index(
        "ix_schema_embeddings_table_id",
        "schema_embeddings",
        ["table_id"],
    )

    op.create_index(
        "ix_schema_embeddings_embedding_status",
        "schema_embeddings",
        ["embedding_status"],
    )

    # =========================
    # RELATIONSHIP GRAPH
    # =========================
    op.create_table(
        "schema_relationship_graph",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("database_id", sa.Integer(), nullable=False),
        sa.Column("source_table_id", sa.Integer(), nullable=False),
        sa.Column("target_table_id", sa.Integer(), nullable=False),
        sa.Column("source_table_name", sa.String(length=255), nullable=False),
        sa.Column("target_table_name", sa.String(length=255), nullable=False),
        sa.Column("source_schema_name", sa.String(length=255), nullable=False),
        sa.Column("target_schema_name", sa.String(length=255), nullable=False),
        sa.Column("relationship_type", sa.String(length=64), nullable=False),
        sa.Column("join_columns", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("relationship_strength", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("path_depth", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_circular", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["database_id"], ["connected_databases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_table_id"], ["database_tables.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_table_id"], ["database_tables.id"], ondelete="CASCADE"),
    )

    op.create_index(
        "ix_schema_relationship_graph_database_id",
        "schema_relationship_graph",
        ["database_id"],
    )

    op.create_index(
        "ix_schema_relationship_graph_source_table_id",
        "schema_relationship_graph",
        ["source_table_id"],
    )

    op.create_index(
        "ix_schema_relationship_graph_target_table_id",
        "schema_relationship_graph",
        ["target_table_id"],
    )

    op.create_index(
        "ix_schema_relationship_graph_relationship_type",
        "schema_relationship_graph",
        ["relationship_type"],
    )

    op.create_index(
        "ix_schema_relationship_graph_is_circular",
        "schema_relationship_graph",
        ["is_circular"],
    )


# =========================
# DOWNGRADE
# =========================
def downgrade() -> None:
    op.drop_table("schema_relationship_graph")
    op.drop_table("schema_embeddings")
    op.drop_table("schema_semantics")
    op.drop_table("sync_logs")
    op.drop_table("database_relationships")
    op.drop_table("database_columns")
    op.drop_table("database_tables")
    op.drop_table("database_schemas")
    op.drop_table("connected_databases")

    op.execute("DROP TYPE IF EXISTS embedding_status_enum")
    op.execute("DROP TYPE IF EXISTS connection_status_enum")
    op.execute("DROP TYPE IF EXISTS database_type_enum")
    op.execute("DROP TYPE IF EXISTS sync_status_enum")
    op.execute("DROP TYPE IF EXISTS table_type_enum")

