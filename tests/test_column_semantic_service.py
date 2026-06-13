from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.column_semantic_service import ColumnSemanticService


def _column(table_name: str = "customers", schema_name: str = "public") -> SimpleNamespace:
    return SimpleNamespace(
        id=10,
        name="email_address",
        data_type="varchar",
        description="Customer email",
        ordinal_position=1,
        table=SimpleNamespace(
            id=1,
            name=table_name,
            description="Customer records",
            table_type=SimpleNamespace(value="table"),
            schema=SimpleNamespace(name=schema_name),
            columns=[],
        ),
    )


def test_parse_table_classification_parses_resolved_columns():
    service = ColumnSemanticService(AsyncMock())
    payload = service._parse_table_classification(
        """
        {
          "table_summary": "Customer master table",
          "business_purpose": "Stores customer contact data",
          "resolved_columns": [
            {
              "column_name": "email_address",
              "is_pii": true,
              "pii_type": "email",
              "risk_level": "high",
              "confidence_score": 0.93,
              "business_meaning": "Customer email",
              "governance_reasoning": "Direct identifier"
            }
          ]
        }
        """
    )
    assert payload["business_purpose"] == "Stores customer contact data"
    assert payload["resolved_columns"][0]["column_name"] == "email_address"


def test_classification_from_column_payload_maps_governance_fields():
    service = ColumnSemanticService(AsyncMock())
    result = service._classification_from_column_payload(
        {
            "column_name": "email_address",
            "is_pii": True,
            "pii_type": "email",
            "risk_level": "high",
            "confidence_score": 0.93,
            "business_meaning": "Customer email",
            "governance_reasoning": "Direct identifier",
        },
        prompt_id="pii_classification",
        prompt_version="2.0",
        model_name="gpt-4o",
        metadata_fingerprint="abc123",
        table_purpose="Stores customer contact data",
    )
    assert result.is_pii is True
    assert result.business_meaning == "Customer email"
    assert result.governance_reasoning == "Direct identifier"
    assert result.table_purpose == "Stores customer contact data"


def test_column_metadata_fingerprint_changes_when_description_changes():
    service = ColumnSemanticService(AsyncMock())
    column = _column()
    table = column.table
    first = service._column_metadata_fingerprint(column, table)
    column.description = "Updated description"
    second = service._column_metadata_fingerprint(column, table)
    assert first != second


def test_needs_classification_skips_unchanged_column():
    service = ColumnSemanticService(AsyncMock())
    column = _column()
    table = column.table
    fingerprint = service._column_metadata_fingerprint(column, table)
    existing = SimpleNamespace(metadata_fingerprint=fingerprint)
    assert service._needs_classification(column, table, existing, force=False) is False


def test_metadata_package_excludes_rulebook_payload():
    service = ColumnSemanticService(AsyncMock())
    column = _column()
    table = column.table
    table.columns = [column]
    database = SimpleNamespace(display_name="Demo DB", name="demo")
    package = service._metadata_package(table, database, None)
    assert "governance_rulebook" not in package
    assert package["columns"][0]["name"] == "email_address"


def test_governance_error_message_normalizes_azure_empty_response():
    service = ColumnSemanticService(AsyncMock())
    assert service._governance_error_message(ValueError("azure_empty_response finish_reason=length")) == "azure_empty_response"
    assert service._governance_error_message(ValueError("empty_ai_response")) == "empty_ai_response"
    assert service._governance_error_message(ValueError("invalid_json")) == "invalid_json"
    assert (
        service._governance_error_message(ValueError("missing_required_sections:resolved_columns"))
        == "missing_required_fields:resolved_columns"
    )


def test_upsert_failed_semantic_persists_error_state_without_fake_pii():
    service = ColumnSemanticService(AsyncMock())
    column = _column()
    table = column.table
    table.columns = [column]
    service.get_by_column_id = AsyncMock(return_value=None)
    service.db.add = lambda row: None
    service.db.flush = AsyncMock()

    row = asyncio.run(
        service._upsert_failed_semantic(
            column,
            database_id=1,
            prompt_id="pii_classification",
            prompt_version="2.0",
            model_name="gpt-5-nano",
            metadata_fingerprint="abc123",
            error_message="empty_ai_response",
            ai_result=None,
        )
    )

    assert row.execution_status == "failed"
    assert row.used_fallback is False
    assert row.error_message == "empty_ai_response"
    assert row.pii_type is None
    assert row.risk_level is None
    assert row.business_meaning is None
    assert row.governance_reasoning is None


def test_classify_table_persists_failed_state_on_empty_ai_response(monkeypatch):
    service = ColumnSemanticService(AsyncMock())
    column = _column()
    table = column.table
    table.columns = [column]
    database = SimpleNamespace(id=1, display_name="Demo DB", name="demo")

    async def fake_generate(self, **kwargs):
        return SimpleNamespace(content="", trace_id="trace-1")

    async def fake_get_by_database_id(_database_id):
        return []

    async def fake_persist_table_failure(columns, database_id, **kwargs):
        return [
            SimpleNamespace(
                column_id=column.id,
                execution_status="failed",
                used_fallback=False,
                error_message=kwargs["error_message"],
            )
        ]

    monkeypatch.setattr(
        "app.services.column_semantic_service.AIObservabilityService.generate",
        fake_generate,
    )
    service.get_by_database_id = fake_get_by_database_id
    service._fetch_database_semantic = AsyncMock(return_value=None)
    service._persist_table_failure = AsyncMock(side_effect=fake_persist_table_failure)
    service.registry.render_prompt = lambda *args, **kwargs: SimpleNamespace(
        metadata=SimpleNamespace(id="pii_classification", version="2.0"),
        system_message="system",
        user_prompt="user",
    )

    results = asyncio.run(service._classify_table(table, database, force=True))

    assert len(results) == 1
    assert results[0].execution_status == "failed"
    assert results[0].used_fallback is False
    assert results[0].error_message == "empty_ai_response"
    service._persist_table_failure.assert_awaited_once()


def test_build_governance_package_groups_pii_columns():
    service = ColumnSemanticService(AsyncMock())
    row = SimpleNamespace(
        is_pii=True,
        pii_type="email",
        risk_level="high",
        business_meaning="Customer email",
        governance_reasoning="Direct identifier",
        table_purpose="Customer contact storage",
        execution_status="success",
    )
    column = SimpleNamespace(name="email_address")
    table = SimpleNamespace(name="customers")
    schema = SimpleNamespace(name="public")
    service.db.execute = AsyncMock(
        return_value=SimpleNamespace(
            all=lambda: [(row, column, table, schema)],
        )
    )
    package = asyncio.run(service.build_governance_package(1))
    assert package["table_count"] == 1
    assert package["packages"][0]["pii_columns"][0]["column_name"] == "email_address"
