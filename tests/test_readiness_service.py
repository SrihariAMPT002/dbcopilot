from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

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
        "governance_readiness_score": 85,
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
    assert any("PII detection readiness" in hint for hint in breakdown.remediation_hints)
    assert any("Ownership metadata" in hint for hint in breakdown.remediation_hints)
