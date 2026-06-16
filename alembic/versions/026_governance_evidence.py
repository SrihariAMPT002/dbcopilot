"""add governance evidence and deterministic pii support

Revision ID: 026_governance_evidence
Revises: 025_add_telemetry_columns
Create Date: 2026-06-15 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "026_governance_evidence"
down_revision = "025_add_telemetry_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "governance_packages",
        sa.Column("evidence", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "governance_packages",
        sa.Column("rule_matches", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "governance_packages",
        sa.Column("sample_patterns", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "governance_packages",
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "governance_packages",
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "governance_packages",
        sa.Column("reasoning_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "governance_packages",
        sa.Column("finish_reason", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "governance_packages",
        sa.Column("latency_ms", sa.Float(), nullable=True),
    )

    op.create_table(
        "governance_evidence",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("governance_package_id", sa.Integer(), sa.ForeignKey("governance_packages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("column_id", sa.Integer(), sa.ForeignKey("database_columns.id", ondelete="CASCADE"), nullable=True),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_source", sa.String(length=64), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "column_statistics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("database_id", sa.Integer(), sa.ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("table_id", sa.Integer(), sa.ForeignKey("database_tables.id", ondelete="CASCADE"), nullable=False),
        sa.Column("column_id", sa.Integer(), sa.ForeignKey("database_columns.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("column_name", sa.String(length=255), nullable=False),
        sa.Column("data_type", sa.String(length=255), nullable=False),
        sa.Column("stats_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "pii_patterns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("pattern_key", sa.String(length=128), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("pattern_type", sa.String(length=32), nullable=False),
        sa.Column("pattern_value", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=False, server_default="medium"),
        sa.Column("confidence_weight", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("pattern_key", name="uq_pii_patterns_pattern_key"),
    )

    op.create_index("ix_governance_evidence_governance_package_id", "governance_evidence", ["governance_package_id"])
    op.create_index("ix_governance_evidence_column_id", "governance_evidence", ["column_id"])
    op.create_index("ix_column_statistics_database_id", "column_statistics", ["database_id"])
    op.create_index("ix_column_statistics_table_id", "column_statistics", ["table_id"])
    op.create_index("ix_column_statistics_column_id", "column_statistics", ["column_id"])
    op.create_index("ix_pii_patterns_pattern_key", "pii_patterns", ["pattern_key"])

    op.bulk_insert(
        sa.table(
            "pii_patterns",
            sa.column("pattern_key", sa.String()),
            sa.column("label", sa.String()),
            sa.column("pattern_type", sa.String()),
            sa.column("pattern_value", sa.Text()),
            sa.column("risk_level", sa.String()),
            sa.column("confidence_weight", sa.Float()),
            sa.column("active", sa.Boolean()),
        ),
        [
            {"pattern_key": "email", "label": "email", "pattern_type": "regex", "pattern_value": r"(?i)[\\w.+-]+@[\\w-]+(?:\\.[\\w-]+)+", "risk_level": "high", "confidence_weight": 0.98, "active": True},
            {"pattern_key": "phone", "label": "phone", "pattern_type": "regex", "pattern_value": r"(?i)(?:\\+?\\d[\\d\\s().-]{7,}\\d)", "risk_level": "high", "confidence_weight": 0.92, "active": True},
            {"pattern_key": "aadhaar", "label": "aadhaar", "pattern_type": "keyword", "pattern_value": "aadhaar", "risk_level": "critical", "confidence_weight": 0.99, "active": True},
            {"pattern_key": "ssn", "label": "ssn", "pattern_type": "keyword", "pattern_value": "ssn|social security", "risk_level": "critical", "confidence_weight": 0.99, "active": True},
            {"pattern_key": "passport", "label": "passport", "pattern_type": "keyword", "pattern_value": "passport", "risk_level": "critical", "confidence_weight": 0.96, "active": True},
            {"pattern_key": "license", "label": "license", "pattern_type": "keyword", "pattern_value": "license", "risk_level": "high", "confidence_weight": 0.88, "active": True},
            {"pattern_key": "upi", "label": "upi", "pattern_type": "keyword", "pattern_value": "upi", "risk_level": "high", "confidence_weight": 0.95, "active": True},
            {"pattern_key": "iban", "label": "iban", "pattern_type": "keyword", "pattern_value": "iban", "risk_level": "high", "confidence_weight": 0.97, "active": True},
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_pii_patterns_pattern_key", table_name="pii_patterns")
    op.drop_index("ix_column_statistics_column_id", table_name="column_statistics")
    op.drop_index("ix_column_statistics_table_id", table_name="column_statistics")
    op.drop_index("ix_column_statistics_database_id", table_name="column_statistics")
    op.drop_index("ix_governance_evidence_column_id", table_name="governance_evidence")
    op.drop_index("ix_governance_evidence_governance_package_id", table_name="governance_evidence")
    op.drop_table("pii_patterns")
    op.drop_table("column_statistics")
    op.drop_table("governance_evidence")

    op.drop_column("governance_packages", "latency_ms")
    op.drop_column("governance_packages", "finish_reason")
    op.drop_column("governance_packages", "reasoning_tokens")
    op.drop_column("governance_packages", "completion_tokens")
    op.drop_column("governance_packages", "prompt_tokens")
    op.drop_column("governance_packages", "sample_patterns")
    op.drop_column("governance_packages", "rule_matches")
    op.drop_column("governance_packages", "evidence")
