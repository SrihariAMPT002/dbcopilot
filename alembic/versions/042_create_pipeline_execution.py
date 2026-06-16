"""create pipeline execution tracking tables

Revision ID: 042_create_pipeline_execution
Revises: 041_add_remediation_actions
Create Date: 2026-06-16
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "042_create_pipeline_execution"
down_revision = "041_add_remediation_actions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pipeline_executions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("database_id", sa.Integer(), sa.ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
        sa.Column("start_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("token_usage_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pipeline_executions_database_id", "pipeline_executions", ["database_id"])
    op.create_index("ix_pipeline_executions_status", "pipeline_executions", ["status"])

    op.create_table(
        "stage_executions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("pipeline_execution_id", sa.Integer(), sa.ForeignKey("pipeline_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("database_id", sa.Integer(), nullable=False),
        sa.Column("stage_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("token_usage_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("execution_order", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_stage_executions_database_id", "stage_executions", ["database_id"])
    op.create_index("ix_stage_executions_stage_name", "stage_executions", ["stage_name"])
    op.create_index("ix_stage_executions_status", "stage_executions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_stage_executions_status", table_name="stage_executions")
    op.drop_index("ix_stage_executions_stage_name", table_name="stage_executions")
    op.drop_index("ix_stage_executions_database_id", table_name="stage_executions")
    op.drop_table("stage_executions")

    op.drop_index("ix_pipeline_executions_status", table_name="pipeline_executions")
    op.drop_index("ix_pipeline_executions_database_id", table_name="pipeline_executions")
    op.drop_table("pipeline_executions")
