"""add semantic evidence and domain scores

Revision ID: 027_semantic_domain_scores
Revises: 026_governance_evidence
Create Date: 2026-06-15 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "027_semantic_domain_scores"
down_revision = "026_governance_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("semantic_packages", sa.Column("domain_scores", sa.Text(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("semantic_packages", sa.Column("evidence", sa.Text(), nullable=False, server_default=sa.text("'[]'")))

    op.add_column("table_semantic_packages", sa.Column("evidence", sa.Text(), nullable=False, server_default=sa.text("'[]'")))

    op.create_table(
        "semantic_evidence",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("semantic_package_id", sa.Integer(), sa.ForeignKey("semantic_packages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("table_id", sa.Integer(), sa.ForeignKey("database_tables.id", ondelete="CASCADE"), nullable=True),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_source", sa.String(length=64), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "business_glossary",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("semantic_package_id", sa.Integer(), sa.ForeignKey("semantic_packages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("term", sa.String(length=255), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="ai"),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("business_glossary")
    op.drop_table("semantic_evidence")
    op.drop_column("table_semantic_packages", "evidence")
    op.drop_column("semantic_packages", "evidence")
    op.drop_column("semantic_packages", "domain_scores")
