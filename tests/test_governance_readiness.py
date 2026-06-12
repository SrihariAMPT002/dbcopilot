from __future__ import annotations

from unittest.mock import AsyncMock

from app.core.config import settings
from app.services.readiness_service import ReadinessService


def test_protection_flags_require_governance_coverage_not_artifact_inventory():
    governance_stats = {
        "column_semantics": 12,
        "pii_columns": 2,
        "pii_typed_columns": 2,
        "pii_risk_tagged_columns": 2,
        "pii_identified_coverage": 100,
        "pii_classified_coverage": 100,
    }
    columns = 12
    completed_tables = 4

    governance_complete = bool(columns > 0 and governance_stats["column_semantics"] >= columns)
    prompt_protection_enabled = bool(settings.pii_prompt_protection_enabled and governance_complete)
    embedding_protection_enabled = bool(
        settings.pii_embedding_protection_enabled and governance_complete and completed_tables > 0
    )

    assert governance_complete is True
    assert prompt_protection_enabled is True
    assert embedding_protection_enabled is True


def test_protection_flags_off_when_governance_incomplete():
    governance_stats = {"column_semantics": 3}
    columns = 12
    governance_complete = bool(columns > 0 and governance_stats["column_semantics"] >= columns)
    prompt_protection_enabled = bool(settings.pii_prompt_protection_enabled and governance_complete)
    assert governance_complete is False
    assert prompt_protection_enabled is False


def test_governance_score_uses_protection_flags():
    service = ReadinessService(AsyncMock())  # type: ignore[name-defined]
    score = service._governance_score(
        {
            "governance": {
                "pii_identified_coverage": 100,
                "pii_classified_coverage": 100,
                "prompt_protection_enabled": True,
                "embedding_protection_enabled": True,
            }
        }
    )
    assert score == 100
