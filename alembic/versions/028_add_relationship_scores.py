"""Add relationship evidence, metrics, and cluster scores.

Revision ID: 028_add_relationship_scores
Revises: 027_semantic_domain_scores
Create Date: 2026-06-15 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "028_add_relationship_scores"
down_revision = "027_semantic_domain_scores"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("relationship_packages", sa.Column("evidence", sa.Text(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column("relationship_packages", sa.Column("graph_metrics", sa.Text(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("relationship_packages", sa.Column("confidence_details", sa.Text(), nullable=False, server_default=sa.text("'{}'")))

    op.create_table(
        "relationship_evidence",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("relationship_package_id", sa.Integer(), sa.ForeignKey("relationship_packages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cluster_id", sa.String(length=128), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_source", sa.String(length=64), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_relationship_evidence_relationship_package_id"), "relationship_evidence", ["relationship_package_id"])
    op.create_index(op.f("ix_relationship_evidence_cluster_id"), "relationship_evidence", ["cluster_id"])

    op.create_table(
        "cluster_scores",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("relationship_package_id", sa.Integer(), sa.ForeignKey("relationship_packages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cluster_id", sa.String(length=128), nullable=False),
        sa.Column("centrality_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("hub_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("community_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("metrics_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_cluster_scores_relationship_package_id"), "cluster_scores", ["relationship_package_id"])
    op.create_index(op.f("ix_cluster_scores_cluster_id"), "cluster_scores", ["cluster_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_cluster_scores_cluster_id"), table_name="cluster_scores")
    op.drop_index(op.f("ix_cluster_scores_relationship_package_id"), table_name="cluster_scores")
    op.drop_table("cluster_scores")

    op.drop_index(op.f("ix_relationship_evidence_cluster_id"), table_name="relationship_evidence")
    op.drop_index(op.f("ix_relationship_evidence_relationship_package_id"), table_name="relationship_evidence")
    op.drop_table("relationship_evidence")

    op.drop_column("relationship_packages", "confidence_details")
    op.drop_column("relationship_packages", "graph_metrics")
    op.drop_column("relationship_packages", "evidence")
