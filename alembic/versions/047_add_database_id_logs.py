"""add database_id to retrieval_logs

Revision ID: 047_add_database_id_logs
Revises: 046_add_graph_fields_indexes
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "047_add_database_id_logs"
down_revision = "046_add_graph_fields_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("retrieval_logs")}
    if "database_id" not in columns:
        op.add_column(
            "retrieval_logs",
            sa.Column("database_id", sa.Integer(), nullable=True),
        )
    indexes = {index["name"] for index in inspector.get_indexes("retrieval_logs")}
    if "ix_retrieval_logs_database_id" not in indexes:
        op.create_index(
            "ix_retrieval_logs_database_id",
            "retrieval_logs",
            ["database_id"],
            unique=False,
        )
    fk_names = {fk["name"] for fk in inspector.get_foreign_keys("retrieval_logs")}
    if "fk_retrieval_logs_database_id_connected_databases" not in fk_names:
        op.create_foreign_key(
            "fk_retrieval_logs_database_id_connected_databases",
            "retrieval_logs",
            "connected_databases",
            ["database_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    fk_names = {fk["name"] for fk in inspector.get_foreign_keys("retrieval_logs")}
    if "fk_retrieval_logs_database_id_connected_databases" in fk_names:
        op.drop_constraint(
            "fk_retrieval_logs_database_id_connected_databases",
            "retrieval_logs",
            type_="foreignkey",
        )
    indexes = {index["name"] for index in inspector.get_indexes("retrieval_logs")}
    if "ix_retrieval_logs_database_id" in indexes:
        op.drop_index("ix_retrieval_logs_database_id", table_name="retrieval_logs")
    columns = {column["name"] for column in inspector.get_columns("retrieval_logs")}
    if "database_id" in columns:
        op.drop_column("retrieval_logs", "database_id")
