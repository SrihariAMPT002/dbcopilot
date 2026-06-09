"""Add analysis_notes to database_semantics.

Revision ID: 004_add_analysis_notes
Revises: 003_add_prompt_studio_artifac
Create Date: 2026-06-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "004_add_analysis_notes"
down_revision = "003_add_prompt_studio_artifac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("database_semantics")}
    if "analysis_notes" not in columns:
        op.add_column("database_semantics", sa.Column("analysis_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("database_semantics")}
    if "analysis_notes" in columns:
        op.drop_column("database_semantics", "analysis_notes")
