from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

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


@pytest.mark.asyncio
async def test_build_governance_package_groups_pii_columns():
    service = ColumnSemanticService(AsyncMock())
    row = SimpleNamespace(
        is_pii=True,
        pii_type="email",
        risk_level="high",
        business_meaning="Customer email",
        governance_reasoning="Direct identifier",
        table_purpose="Customer contact storage",
    )
    column = SimpleNamespace(name="email_address")
    table = SimpleNamespace(name="customers")
    schema = SimpleNamespace(name="public")
    service.db.execute = AsyncMock(
        return_value=SimpleNamespace(
            all=lambda: [(row, column, table, schema)],
        )
    )
    package = await service.build_governance_package(1)
    assert package["table_count"] == 1
    assert package["packages"][0]["pii_columns"][0]["column_name"] == "email_address"
