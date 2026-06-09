
from alembic import op
import sqlalchemy as sa


revision = "005_add_column_semantics"
down_revision = "004_add_analysis_notes" 
branch_labels = None
depends_on = None
def upgrade() -> None:
    op.create_table(
        "column_semantics",

        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "column_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "database_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "business_name",
            sa.String(255),
            nullable=True,
        ),

        sa.Column(
            "business_description",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "column_category",
            sa.String(100),
            nullable=True,
        ),

        sa.Column(
            "table_category",
            sa.String(100),
            nullable=True,
        ),

        sa.Column(
            "is_pii",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),

        sa.Column(
            "pii_type",
            sa.String(100),
            nullable=True,
        ),

        sa.Column(
            "risk_level",
            sa.String(50),
            nullable=True,
        ),

        sa.Column(
            "confidence_score",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.0"),
        ),

        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),

        sa.PrimaryKeyConstraint("id"),

        sa.ForeignKeyConstraint(
            ["column_id"],
            ["database_columns.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["database_id"],
            ["connected_databases.id"],
            ondelete="CASCADE",
        ),

        sa.UniqueConstraint(
            "column_id",
            name="uq_column_semantics_column_id",
        ),
    )

    op.create_index(
        "ix_column_semantics_column_id",
        "column_semantics",
        ["column_id"],
    )

    op.create_index(
        "ix_column_semantics_database_id",
        "column_semantics",
        ["database_id"],
    )

    op.create_index(
        "ix_column_semantics_is_pii",
        "column_semantics",
        ["is_pii"],
    )

    op.create_index(
        "ix_column_semantics_column_category",
        "column_semantics",
        ["column_category"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_column_semantics_column_category",
        table_name="column_semantics",
    )

    op.drop_index(
        "ix_column_semantics_is_pii",
        table_name="column_semantics",
    )

    op.drop_index(
        "ix_column_semantics_database_id",
        table_name="column_semantics",
    )

    op.drop_index(
        "ix_column_semantics_column_id",
        table_name="column_semantics",
    )

    op.drop_table("column_semantics")