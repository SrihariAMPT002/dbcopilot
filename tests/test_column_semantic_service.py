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
        table=SimpleNamespace(
            name=table_name,
            description="Customer records",
            table_type=SimpleNamespace(value="table"),
            schema=SimpleNamespace(name=schema_name),
        ),
    )


def test_parse_classification_from_llm_json():
    service = ColumnSemanticService(AsyncMock())
    result = service._parse_classification(
        '{"is_pii": true, "pii_type": "Email", "risk_level": "high", "confidence_score": 0.93}',
        "pii_classification",
        "1.0",
        "gpt-4o",
        "abc123",
    )
    assert result.is_pii is True
    assert result.pii_type == "Email"
    assert result.risk_level == "high"
    assert result.confidence_score == 0.93
    assert result.metadata_fingerprint == "abc123"


def test_parse_classification_defaults_non_pii_on_invalid_json():
    service = ColumnSemanticService(AsyncMock())
    result = service._parse_classification("not-json", "pii_classification", "1.0", "gpt-4o", "fp")
    assert result.is_pii is False
    assert result.pii_type is None
    assert result.confidence_score == 0.0


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
