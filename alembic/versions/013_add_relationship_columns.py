"""Add relationship columns to schema_relationship_graph.

Revision ID: 013_add_relationship_columns
Revises: 012_add_overall_score
Create Date: 2026-06-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "013_add_relationship_columns"
down_revision = "012_add_overall_score"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("schema_relationship_graph", sa.Column("business_entity_graph", sa.Text(), nullable=True))
    op.add_column("schema_relationship_graph", sa.Column("business_process_flows", sa.Text(), nullable=True))
    op.add_column("schema_relationship_graph", sa.Column("upstream_dependencies", sa.Text(), nullable=True))
    op.add_column("schema_relationship_graph", sa.Column("downstream_dependencies", sa.Text(), nullable=True))
    op.add_column("schema_relationship_graph", sa.Column("entity_lifecycle_descriptions", sa.Text(), nullable=True))
    op.add_column("schema_relationship_graph", sa.Column("ai_summary", sa.Text(), nullable=True))
    op.add_column("schema_relationship_graph", sa.Column("ai_confidence", sa.Float(), nullable=True))
    op.add_column("schema_relationship_graph", sa.Column("ai_model_name", sa.String(length=255), nullable=True))
    op.add_column("schema_relationship_graph", sa.Column("ai_prompt_id", sa.String(length=255), nullable=True))
    op.add_column("schema_relationship_graph", sa.Column("ai_prompt_version", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("schema_relationship_graph", "ai_prompt_version")
    op.drop_column("schema_relationship_graph", "ai_prompt_id")
    op.drop_column("schema_relationship_graph", "ai_model_name")
    op.drop_column("schema_relationship_graph", "ai_confidence")
    op.drop_column("schema_relationship_graph", "ai_summary")
    op.drop_column("schema_relationship_graph", "entity_lifecycle_descriptions")
    op.drop_column("schema_relationship_graph", "downstream_dependencies")
    op.drop_column("schema_relationship_graph", "upstream_dependencies")
    op.drop_column("schema_relationship_graph", "business_process_flows")
    op.drop_column("schema_relationship_graph", "business_entity_graph")
