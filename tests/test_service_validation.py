from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import func, select

from app.models.artifact_manifest import ArtifactType
from app.models.metadata import (
    ConnectedDatabase,
    ColumnSemantic,
    DatabaseSemantic,
    DatabaseTable,
    GovernancePackage,
    RelationshipPackage,
    SchemaRelationshipGraph,
    DatabaseSchema,
    KPIIntelligence,
    DatabaseColumn,
    DatabaseRelationship,
    SemanticPackage,
)
from app.services.kpi_intelligence_service import KPIIntelligenceService
from app.services.prompt_studio_service import PromptStudioService
from app.services.readiness_service import ReadinessService
from app.services.database_semantic_service import DatabaseSemanticService
from app.services.ai_observability_service import AIObservationResult
from app.services.prompt_studio_service import ContextPackageResult


def test_governance_package_failure_reason_alias() -> None:
    package = GovernancePackage()
    package.failure_reason = "missing context"

    assert package.raw_failure_reason == "missing context"
    assert package.failure_reason == "missing context"


def test_relationship_package_legacy_aliases() -> None:
    package = SchemaRelationshipGraph()
    package.entity_graph = [{"left": "a", "right": "b"}]
    package.lifecycle_flows = [{"name": "flow"}]

    assert package.business_entity_graph_alias == [{"left": "a", "right": "b"}]
    assert package.entity_lifecycle_descriptions_alias == [{"name": "flow"}]


def test_core_service_constructors_init() -> None:
    db = AsyncMock()

    PromptStudioService(db)
    KPIIntelligenceService(db)
    ReadinessService(db)


def test_kpi_parser_accepts_partial_payload() -> None:
    parsed = KPIIntelligenceService._parse_required_json(
        """
        {
          "kpi_catalog": [
            {"name": "Revenue", "description": "Revenue KPI", "formula": "SUM(amount)"}
          ]
        }
        """
    )

    assert parsed["kpi_catalog"][0]["name"] == "Revenue"
    assert parsed["kpi_definitions"] == []
    assert parsed["kpi_lineage"] == []
    assert parsed["kpi_context"] == ""


def test_kpi_cluster_handles_non_json_ai_output() -> None:
    service = KPIIntelligenceService(AsyncMock())
    database = SimpleNamespace(id=1, display_name="Demo", name="Demo")
    rendered = SimpleNamespace(metadata=SimpleNamespace(id="kpi_discovery", version="clustered"))
    ai_result = SimpleNamespace(
        content="not json",
        token_usage={"prompt_tokens": 12, "completion_tokens": 34},
        trace_id=None,
        model_name="gpt-5-nano",
    )

    with patch.object(service, "_fetch_governance_packages", AsyncMock(return_value=[])), patch.object(service, "_fetch_semantic_package", AsyncMock(return_value=None)), patch.object(service, "_fetch_relationship_packages", AsyncMock(return_value=[])), patch.object(service, "_cluster_prompt_context", return_value={
        "database_id": 1,
        "database_name": "Demo",
        "semantic_domain": "sales",
        "cluster_id": "cluster-1",
        "cluster_name": "cluster-1",
        "cluster_table_count": 0,
        "cluster_tables": [],
        "cluster_relationships": [],
        "database_semantics": {},
        "semantic_package": {},
        "governance_packages": [],
        "governance_intelligence": [],
        "kpi_candidates": [],
    }), patch.object(service, "_apply_cluster_budget", return_value=({
        "database_id": 1,
        "database_name": "Demo",
        "semantic_domain": "sales",
        "cluster_id": "cluster-1",
        "cluster_name": "cluster-1",
        "cluster_table_count": 0,
        "cluster_tables": [],
        "cluster_relationships": [],
        "database_semantics": {},
        "semantic_package": {},
        "governance_packages": [],
        "governance_intelligence": [],
        "kpi_candidates": [],
    }, {"cluster_size": 0, "estimated_tokens": 0, "prompt_truncated": False})), patch.object(service, "_call_azure_openai", AsyncMock(return_value=ai_result)):
        result = asyncio.run(service._discover_for_cluster(
            database=database,
            cluster_id="cluster-1",
            table_ids=[],
            semantics=(None, []),
            column_semantics=[],
            job_id=None,
            governance_packages=[],
            semantic_package=None,
            relationship_packages=[],
            candidates=[],
        ))

    assert result["execution_status"] == "success"
    assert result["fallback_used"] is True
    assert result["catalog"] == []
    assert "parse_warning" in result


def test_context_package_result_allows_partial_metadata() -> None:
    result = ContextPackageResult(
        artifact_type=ArtifactType.system_prompt,
        content="hello",
        mime="text/plain",
        filename="prompt.txt",
        context_quality_score=0.75,
        governance_coverage=0.5,
        pii_coverage=0.25,
        generated_at=datetime.now(timezone.utc),
    )

    assert result.prompt_id is None
    assert result.prompt_version is None
    assert result.model_name is None
    assert result.trace_id is None
    assert result.prompt_tokens == 0
    assert result.completion_tokens == 0
    assert result.reasoning_tokens == 0


def test_prompt_normalizer_handles_empty_ai_artifact() -> None:
    normalized = PromptStudioService._normalize_ai_artifact(None)

    assert normalized["prompt_id"] is None
    assert normalized["prompt_version"] == "1.0"
    assert normalized["execution_status"] == "partial"
    assert normalized["trace_id"] is None


def test_prompt_normalizer_defaults_missing_prompt_id() -> None:
    normalized = PromptStudioService._normalize_ai_artifact({"template_id": "template-42"})

    assert normalized["prompt_id"] == "template-42"


def test_readiness_collect_stats_compiles_successfully() -> None:
    db = AsyncMock()
    scalar_statements = []
    execute_statements = []

    async def _scalar_side_effect(stmt, *args, **kwargs):
        scalar_statements.append(stmt)
        str(stmt.compile(compile_kwargs={"literal_binds": True}))
        return 0

    def _empty_rows_result(first_result=None):
        scalars = SimpleNamespace(first=lambda: first_result, all=lambda: [])
        return SimpleNamespace(all=lambda: [], scalars=lambda: scalars)

    async def _execute_side_effect(stmt, *args, **kwargs):
        execute_statements.append(stmt)
        str(stmt.compile(compile_kwargs={"literal_binds": True}))
        return _empty_rows_result()

    db.scalar = AsyncMock(side_effect=_scalar_side_effect)
    db.execute = AsyncMock(side_effect=_execute_side_effect)

    service = ReadinessService(db)
    with patch.object(service, "_fetch_database", AsyncMock(return_value=SimpleNamespace(
        id=1,
        display_name="Demo",
        name="Demo",
        db_type=SimpleNamespace(value="postgresql"),
        last_sync_at=None,
    ))), patch.object(service, "_fetch_governance_packages", AsyncMock(return_value=[])), patch.object(service, "_fetch_semantic_package", AsyncMock(return_value=None)), patch.object(service, "_fetch_relationship_packages", AsyncMock(return_value=[])), patch.object(service, "_fetch_database_semantic", AsyncMock(return_value=None)), patch.object(service, "_readiness_prompt_names", return_value=[]), patch("app.services.readiness_service.EmbeddingEngine.get_embedding_status", AsyncMock(return_value={
        "indexed_tables": 0,
        "completed_tables": 0,
        "failed_tables": 0,
        "vectors_total": 0,
        "vector_counts": {},
        "collections": [],
        "qdrant_health": False,
        "embedding_health": False,
        "total_tables": 0,
    })), patch("app.services.readiness_service.PromptStudioService._artifact_order", return_value=[]):
        stats = asyncio.run(service._collect_stats(1))

    assert stats["kpi"]["kpi_cluster_count"] == 0
    assert stats["metadata"]["schemas"] == 0
    for stmt in scalar_statements + execute_statements:
        str(stmt.compile())


def test_readiness_collect_stats_query_shapes_compile_without_execution() -> None:
    service = ReadinessService(AsyncMock())
    statements = [
        select(DatabaseSchema.id).where(DatabaseSchema.connected_db_id == 1),
        select(DatabaseTable.id).select_from(DatabaseTable).join(DatabaseSchema).where(DatabaseSchema.connected_db_id == 1),
        select(DatabaseColumn.id).select_from(DatabaseColumn).join(DatabaseTable).join(DatabaseSchema).where(DatabaseSchema.connected_db_id == 1),
        select(DatabaseRelationship.id).select_from(DatabaseRelationship).join(DatabaseTable, DatabaseRelationship.table_id == DatabaseTable.id).join(DatabaseSchema, DatabaseTable.schema_id == DatabaseSchema.id).where(DatabaseSchema.connected_db_id == 1),
        select(func.avg(KPIIntelligence.confidence)).select_from(KPIIntelligence).where(KPIIntelligence.database_id == 1),
        select(KPIIntelligence.cluster_id, KPIIntelligence.execution_status).select_from(KPIIntelligence).where(KPIIntelligence.database_id == 1),
    ]

    for stmt in statements:
        assert str(stmt.compile(compile_kwargs={"literal_binds": True})) is not None


def test_kpi_query_shapes_compile_without_recursion() -> None:
    statements = [
        select(KPIIntelligence).where(KPIIntelligence.database_id == 1).order_by(KPIIntelligence.name),
        select(KPIIntelligence.cluster_id, KPIIntelligence.execution_status).select_from(KPIIntelligence).where(KPIIntelligence.database_id == 1),
        select(func.count()).select_from(KPIIntelligence).where(KPIIntelligence.database_id == 1),
        select(func.avg(KPIIntelligence.confidence)).select_from(KPIIntelligence).where(KPIIntelligence.database_id == 1),
    ]

    for stmt in statements:
        assert str(stmt.compile(compile_kwargs={"literal_binds": True})) is not None


def test_prompt_studio_query_shapes_compile_without_recursion() -> None:
    statements = [
        select(ConnectedDatabase),
        select(DatabaseSemantic).where(DatabaseSemantic.source_id == 1),
        select(SemanticPackage).where(SemanticPackage.database_id == 1),
        select(ColumnSemantic).where(ColumnSemantic.database_id == 1),
        select(DatabaseTable).where(DatabaseTable.schema_id == 1),
        select(GovernancePackage).where(GovernancePackage.database_id == 1),
        select(RelationshipPackage).where(RelationshipPackage.database_id == 1),
        select(KPIIntelligence).where(KPIIntelligence.database_id == 1),
    ]

    for stmt in statements:
        assert str(stmt.compile(compile_kwargs={"literal_binds": True})) is not None


def test_readiness_normalizer_handles_missing_prompt_metadata() -> None:
    normalized = ReadinessService._normalize_ai_artifact(
        {
            "ai_summary": "ok",
            "ai_recommendations": ["r1"],
            "token_metrics": {"prompt_tokens": 10},
        }
    )

    assert normalized["prompt_id"] is None
    assert normalized["trace_id"] is None
    assert normalized["token_metrics"] == {"prompt_tokens": 10}
    assert normalized["ai_summary"] == "ok"


def test_database_semantic_parser_handles_sparse_response() -> None:
    service = DatabaseSemanticService(AsyncMock())
    enrichment = service._parse_enrichment_response(
        1,
        """
        {
          "business_domain": "Finance",
          "semantic_summary": "Accounts and balances"
        }
        """
    )

    assert enrichment.source_id == 1
    assert enrichment.business_domain == "Finance"
    assert enrichment.business_summary == "Accounts and balances"
    assert enrichment.prompt_id is None
    assert enrichment.trace_id is None
