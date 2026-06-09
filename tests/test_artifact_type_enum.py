from __future__ import annotations

from app.models.artifact_manifest import ArtifactManifest, ArtifactType, artifact_type_enum_values


def test_artifact_type_enum_values_match_database_labels() -> None:
    assert artifact_type_enum_values() == [
        "semantic_summary.json",
        "embeddings.json",
        "relationship_graph.json",
        "prompt_context.md",
        "database_context.md",
        "system_prompt.md",
        "rag_context.md",
        "agent_context.json",
        "text_to_sql_context.md",
    ]


def test_artifact_type_resolve_accepts_value_and_name() -> None:
    assert ArtifactType.resolve("database_context.md") == ArtifactType.database_context
    assert ArtifactType.resolve("database_context") == ArtifactType.database_context


def test_artifact_type_query_binds_persisted_value() -> None:
    from sqlalchemy.dialects import postgresql

    column = ArtifactManifest.__table__.c.artifact_type
    bind_processor = column.type.bind_processor(postgresql.dialect())

    assert ArtifactType.database_context.value == "database_context.md"
    assert bind_processor(ArtifactType.database_context) == "database_context.md"
