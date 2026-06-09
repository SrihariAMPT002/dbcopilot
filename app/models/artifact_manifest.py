"""
Artifact manifest model for versioned AI context packages.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.metadata import Base


class ArtifactType(str, enum.Enum):
    semantic_summary = "semantic_summary.json"
    embeddings = "embeddings.json"
    relationship_graph = "relationship_graph.json"
    prompt_context = "prompt_context.md"
    database_context = "database_context.md"
    system_prompt = "system_prompt.md"
    rag_context = "rag_context.md"
    agent_context = "agent_context.json"
    text_to_sql_context = "text_to_sql_context.md"

    @classmethod
    def resolve(cls, value: str | ArtifactType) -> ArtifactType:
        """Resolve an enum member from its persisted value or member name."""
        if isinstance(value, cls):
            return value
        for member in cls:
            if value == member.value or value == member.name:
                return member
        raise ValueError(f"Unknown artifact type: {value!r}")


def artifact_type_enum_values(enum_cls: type[ArtifactType] | None = None) -> list[str]:
    """Return persisted PostgreSQL enum labels (member values, not names)."""
    cls = enum_cls or ArtifactType
    return [member.value for member in cls]


class ExportStatus(str, enum.Enum):
    queued = "QUEUED"
    running = "RUNNING"
    completed = "COMPLETED"
    failed = "FAILED"


class ArtifactManifest(Base):
    __tablename__ = "artifact_manifests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    database_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("connected_databases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_type: Mapped[ArtifactType] = mapped_column(
        Enum(
            ArtifactType,
            name="artifact_type_enum",
            values_callable=artifact_type_enum_values,
        ),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    schema_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    prompt_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    def export_status_enum_values(enum_cls):
        return [e.value for e in enum_cls]

    export_status: Mapped[ExportStatus] = mapped_column(
        Enum(
            ExportStatus,
            name="artifact_export_status_enum",
            values_callable=export_status_enum_values,
        ),
        nullable=False,
    )
    artifact_path: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
