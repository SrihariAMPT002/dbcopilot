from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.prompt_studio_service import PromptStudioService
from app.models.artifact_manifest import ArtifactType


@pytest.mark.asyncio
async def test_prompt_templates_load() -> None:
    service = PromptStudioService(AsyncMock())
    templates = await service.list_templates()

    template_ids = {item["id"] for item in templates}
    assert {"database_context", "system_prompt", "rag_context", "agent_context", "text_to_sql"} <= template_ids


@pytest.mark.asyncio
async def test_generate_artifacts_renders_all_outputs(monkeypatch: pytest.MonkeyPatch) -> None:
    service = PromptStudioService(AsyncMock())
    service._build_context = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "database_id": 1,
            "database_name": "Demo DB",
            "database_type": "postgresql",
            "generated_at": "2026-06-01T00:00:00+00:00",
            "schema_count": 1,
            "table_count": 1,
            "column_count": 2,
            "relationship_count": 0,
            "semantic": {
                "business_domain": "CRM",
                "business_summary": "Tracks customers and tickets.",
                "confidence_score": 0.91,
                "generation_status": "completed",
                "key_entities": ["customers", "tickets"],
                "business_glossary": [{"term": "ticket", "definition": "Support request"}],
                "suggested_use_cases": ["Search support issues"],
            },
            "relationship_graph": {
                "metrics": {
                    "table_count": 1,
                    "edge_count": 0,
                    "graph_depth": 0,
                    "central_tables": ["public.customers"],
                    "isolated_tables": [],
                },
                "edges": [],
            },
            "embeddings": {
                "indexed_tables": 1,
                "vector_count": 3,
                "embedding_model": "text-embedding-3-small",
                "qdrant_health": True,
                "collection_names": ["schema_tables"],
            },
            "tables": [
                {
                    "schema_name": "public",
                    "table_name": "customers",
                    "table_type": "table",
                    "relevant_columns": ["id", "name"],
                    "semantic_status": "completed",
                    "embedding_status": "completed",
                }
            ],
        }
    )
    service.artifact_service.record_artifact = AsyncMock(side_effect=lambda *args, **kwargs: {  # type: ignore[method-assign]
        "id": 1,
        "artifact_type": args[1].value,
        "version": 1,
        "schema_hash": "abc",
        "export_status": "COMPLETED",
        "artifact_path": "/tmp/demo",
        "generated_at": "2026-06-01T00:00:00+00:00",
        "filename": "demo",
        "mime": kwargs.get("mime", "text/plain"),
        "content": args[2],
    })

    artifacts = await service.generate_artifacts(1)

    assert len(artifacts) == 5
    assert {item["artifact_type"] for item in artifacts} == {
        ArtifactType.database_context.value,
        ArtifactType.system_prompt.value,
        ArtifactType.rag_context.value,
        ArtifactType.agent_context.value,
        ArtifactType.text_to_sql_context.value,
    }
    assert service.artifact_service.record_artifact.await_count == 5

    agent_context = next(
        item for item in artifacts if item["artifact_type"] == ArtifactType.agent_context.value
    )
    parsed = json.loads(agent_context["content"])
    assert parsed["database"]["name"] == "Demo DB"
