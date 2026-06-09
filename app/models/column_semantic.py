from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.metadata import Base


class ColumnSemantic(Base):
    __tablename__ = "column_semantics"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    column_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "database_columns.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    database_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "connected_databases.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    business_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    business_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    prompt_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    prompt_version: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    model_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    column_category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    table_category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    is_pii: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    pii_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    risk_level: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    confidence_score: Mapped[float] = mapped_column(
        nullable=False,
        default=0.0,
    )

    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
