from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.database_semantic_service import DatabaseSemanticService


def test_parse_enrichment_response_maps_semantic_package():
    service = DatabaseSemanticService(AsyncMock())
    enrichment = service._parse_enrichment_response(
        1,
        """
        {
          "business_domain": "Healthcare",
          "business_capabilities": ["Patient intake", "Billing"],
          "business_entities": ["patients", "appointments"],
          "business_processes": ["Patient registration", "Claims processing"],
          "semantic_summary": "Clinical operations database",
          "table_semantics": [
            {
              "schema_name": "public",
              "table_name": "patients",
              "semantic_summary": "Patient master",
              "business_entities": ["patient"],
              "business_processes": ["registration"],
              "business_capabilities": ["intake"]
            }
          ]
        }
        """,
    )
    assert enrichment.business_domain == "Healthcare"
    assert enrichment.business_summary == "Clinical operations database"
    assert enrichment.key_entities == ["patients", "appointments"]
    assert enrichment.suggested_use_cases == ["Patient intake", "Billing"]
    assert enrichment.business_processes == ["Patient registration", "Claims processing"]
    assert enrichment.table_semantics[0]["table_name"] == "patients"


def test_build_prompt_variables_uses_metadata_and_governance_only():
    service = DatabaseSemanticService(AsyncMock())
    database = SimpleNamespace(display_name="Demo DB", name="demo")
    variables = service._build_prompt_variables(
        database,
        {
            "metadata": {"table_count": 2, "tables": []},
            "governance_package": {"table_count": 2, "packages": []},
        },
    )
    assert "metadata" in variables
    assert "governance_package" in variables
    assert "schema_summary" not in variables


@pytest.mark.asyncio
async def test_build_semantic_input_includes_pii_columns_without_schema_dump(monkeypatch: pytest.MonkeyPatch):
    service = DatabaseSemanticService(AsyncMock())
    pii_row = SimpleNamespace(is_pii=True, pii_type="email", risk_level="high", business_meaning="Contact email")

    governance_mock = AsyncMock(return_value={"database_id": 1, "table_count": 1, "packages": []})
    pii_mock = AsyncMock(return_value={10: pii_row})
    monkeypatch.setattr(
        "app.services.database_semantic_service.ColumnSemanticService.build_governance_package",
        governance_mock,
    )
    monkeypatch.setattr(
        "app.services.database_semantic_service.ColumnSemanticService.get_pii_map",
        pii_mock,
    )

    column = SimpleNamespace(id=10, name="email", data_type="varchar", description="Email")
    table = SimpleNamespace(
        name="customers",
        description="Customer records",
        table_type=SimpleNamespace(value="table"),
        columns=[column],
        relationships_from=[],
    )
    schema = SimpleNamespace(name="public", description=None, tables=[table])
    database = SimpleNamespace(
        id=1,
        display_name="Demo",
        name="demo",
        db_type=SimpleNamespace(value="postgresql"),
        schemas=[schema],
    )

    payload = await service._build_semantic_input(database)
    table_entry = payload["metadata"]["tables"][0]
    assert table_entry["pii_columns"][0]["name"] == "email"
    assert "columns" not in table_entry
    assert payload["governance_package"]["table_count"] == 1
