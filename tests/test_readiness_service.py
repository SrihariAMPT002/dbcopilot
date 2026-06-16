from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config.manager import get_config_manager
from app.config.package_registry import get_package_registry
from app.models.readiness_snapshot import ReadinessStatus
from app.services.readiness_service import ReadinessService


def _good_stats() -> dict:
    return {
        "metadata": {
            "schemas": 2,
            "tables": 4,
            "columns": 12,
            "relationships": 3,
            "schemas_with_description": 2,
            "tables_with_description": 4,
            "columns_with_description": 12,
            "tables_with_row_count": 4,
            "primary_key_columns": 4,
            "foreign_key_columns": 3,
            "indexed_columns": 6,
        },
        "semantic": {
            "schema_semantics": 4,
            "semantic_table_coverage": 100,
            "profile": {
                "has_profile": True,
                "business_domain": True,
                "business_summary": True,
                "analysis_notes": True,
                "key_entities": 4,
                "business_glossary": 4,
                "suggested_use_cases": 4,
                "confidence_score": 0.92,
                "generation_status": "completed",
            },
        },
        "relationships": {
            "graph_edges": 3,
            "graph_table_coverage": 100,
            "graph_density": 0.5,
            "graph_cycles": 0,
            "isolated_tables": 0,
            "graph_table_ids": 4,
        },
        "ai_context": {
            "prompt_artifacts_rendered": 5,
            "prompt_artifacts_expected": 5,
            "prompt_context_length": 1200,
            "prompt_artifact_errors": [],
            "embedding_coverage": 100,
            "semantic_dependency_coverage": 100,
        },
        "governance": {
            "column_semantics": 12,
            "pii_columns": 2,
            "pii_typed_columns": 2,
            "pii_risk_tagged_columns": 2,
            "pii_identified_coverage": 100,
            "pii_classified_coverage": 100,
            "prompt_protection_enabled": True,
            "embedding_protection_enabled": True,
            "documentation_coverage": 100,
            "ownership_coverage": 0,
            "ownership_metadata_present": False,
            "pii_coverage": 100,
        },
        "embeddings": {
            "indexed_tables": 4,
            "completed_tables": 4,
            "failed_tables": 0,
            "vectors_total": 12,
            "qdrant_health": True,
            "embedding_health": True,
            "total_tables": 4,
            "collections": [],
            "vector_counts": {},
        },
        "nosql": {
            "collections": 0,
            "nested_fields": 0,
            "relationships": 0,
        },
        "database_semantic": None,
    }


def _gap_stats() -> dict:
    return {
        "metadata": {
            "schemas": 1,
            "tables": 2,
            "columns": 4,
            "relationships": 0,
            "schemas_with_description": 0,
            "tables_with_description": 0,
            "columns_with_description": 0,
            "tables_with_row_count": 0,
            "primary_key_columns": 1,
            "foreign_key_columns": 0,
            "indexed_columns": 0,
        },
        "semantic": {
            "schema_semantics": 0,
            "semantic_table_coverage": 0,
            "profile": {
                "has_profile": False,
                "business_domain": False,
                "business_summary": False,
                "analysis_notes": False,
                "key_entities": 0,
                "business_glossary": 0,
                "suggested_use_cases": 0,
                "confidence_score": 0.0,
                "generation_status": "not_generated",
            },
        },
        "relationships": {
            "graph_edges": 0,
            "graph_table_coverage": 0,
            "graph_density": 0,
            "graph_cycles": 0,
            "isolated_tables": 2,
            "graph_table_ids": 0,
        },
        "ai_context": {
            "prompt_artifacts_rendered": 0,
            "prompt_artifacts_expected": 5,
            "prompt_context_length": 0,
            "prompt_artifact_errors": ["database_context: render failed"],
            "embedding_coverage": 0,
            "semantic_dependency_coverage": 0,
        },
        "governance": {
            "column_semantics": 0,
            "pii_columns": 0,
            "pii_typed_columns": 0,
            "pii_risk_tagged_columns": 0,
            "pii_identified_coverage": 0,
            "pii_classified_coverage": 0,
            "prompt_protection_enabled": False,
            "embedding_protection_enabled": False,
            "documentation_coverage": 0,
            "ownership_coverage": 0,
            "ownership_metadata_present": False,
            "pii_coverage": 0,
        },
        "embeddings": {
            "indexed_tables": 0,
            "completed_tables": 0,
            "failed_tables": 0,
            "vectors_total": 0,
            "qdrant_health": False,
            "embedding_health": False,
            "total_tables": 2,
            "collections": [],
            "vector_counts": {},
        },
        "nosql": {
            "collections": 0,
            "nested_fields": 0,
            "relationships": 0,
        },
        "database_semantic": None,
    }


@pytest.mark.asyncio
async def test_readiness_breakdown_reports_category_scores():
    session = AsyncMock()
    service = ReadinessService(session)

    service._fetch_database = AsyncMock(
        return_value=SimpleNamespace(
            id=1,
            name="demo_db",
            display_name="Demo DB",
            last_sync_at=None,
        )
    )
    service._collect_stats = AsyncMock(return_value=_good_stats())

    breakdown = await service._build_breakdown(1)

    assert breakdown.readiness_status == ReadinessStatus.READY
    assert breakdown.category_scores == {
        "metadata_readiness_score": 100,
        "semantic_readiness_score": 100,
        "relationship_readiness_score": 100,
        "ai_context_readiness_score": 100,
        "governance_readiness_score": 100,
        "kpi_readiness_score": 0,
    }
    assert breakdown.overall_score >= 90
    assert breakdown.missing_stages == []
    assert breakdown.details["metadata"]["schemas"] == 2


@pytest.mark.asyncio
async def test_readiness_breakdown_surfaces_missing_stages():
    session = AsyncMock()
    service = ReadinessService(session)

    service._fetch_database = AsyncMock(
        return_value=SimpleNamespace(
            id=1,
            name="demo_db",
            display_name="Demo DB",
            last_sync_at=None,
        )
    )
    service._collect_stats = AsyncMock(return_value=_gap_stats())

    breakdown = await service._build_breakdown(1)

    assert breakdown.readiness_status == ReadinessStatus.NOT_READY
    assert "metadata" in breakdown.missing_stages
    assert "semantic" in breakdown.missing_stages
    assert "relationships" in breakdown.missing_stages
    assert "ai_context" in breakdown.missing_stages
    assert "governance" in breakdown.missing_stages
    assert any("PII intelligence" in hint for hint in breakdown.remediation_hints)
    assert any("Ownership metadata" in hint for hint in breakdown.remediation_hints)


@pytest.mark.asyncio
async def test_get_or_compute_hydrates_snapshot_ai_fields():
    session = AsyncMock()
    service = ReadinessService(session)

    snapshot = SimpleNamespace(
        readiness_status=ReadinessStatus.READY,
        generated_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
        ai_summary="Persisted AI summary",
        ai_recommendations='["Improve semantic coverage"]',
        ai_risks='["KPI freshness is stale"]',
        ai_roadmap='["Refresh KPI artifacts"]',
        ai_confidence=0.87,
        prompt_id="readiness_assessment",
        prompt_version="2.0",
        model_name="gpt-5-nano",
    )

    service._latest_snapshot = AsyncMock(return_value=snapshot)
    service._fetch_database = AsyncMock(
        return_value=SimpleNamespace(
            id=1,
            name="demo_db",
            display_name="Demo DB",
            last_sync_at=None,
        )
    )
    service._collect_stats = AsyncMock(return_value=_good_stats())

    breakdown = await service.get_or_compute(1)

    assert breakdown.ai_summary == "Persisted AI summary"
    assert breakdown.ai_recommendations == ["Improve semantic coverage"]
    assert breakdown.ai_risks == ["KPI freshness is stale"]
    assert breakdown.ai_roadmap == ["Refresh KPI artifacts"]
    assert breakdown.ai_confidence == 0.87
    assert breakdown.prompt_id == "readiness_assessment"
    assert breakdown.prompt_version == "2.0"
    assert breakdown.model_name == "gpt-5-nano"
    assert service._collect_stats.await_count == 1


@pytest.mark.asyncio
async def test_collect_stats_empty_database_has_zero_snapshot_count():
    session = AsyncMock()
    service = ReadinessService(session)

    service._fetch_governance_packages = AsyncMock(return_value=[])
    service._fetch_semantic_package = AsyncMock(return_value=None)
    service._fetch_relationship_packages = AsyncMock(return_value=[])
    service.db.scalar = AsyncMock(return_value=0)

    stats = await service._collect_stats(1)

    assert stats["metadata"]["schemas"] == 0
    assert stats["semantic"]["schema_semantics"] == 0
    assert stats["relationships"]["graph_edges"] == 0
    assert stats["ai_context"]["prompt_artifacts_rendered"] == 0
    assert stats["governance"]["column_semantics"] == 0
    assert stats["kpi"]["kpi_cluster_count"] == 0
    assert stats["embeddings"]["completed_tables"] == 0


def test_readiness_dimensions_match_enabled_packages():
    readiness = get_config_manager().get_readiness_rules()["readiness"]
    dimensions = readiness["dimensions"]
    packages = get_package_registry().get("packages", {})
    enabled = [name for name, package in packages.items() if package.get("readiness_enabled", False)]
    assert sorted(dimensions) == sorted(enabled)
