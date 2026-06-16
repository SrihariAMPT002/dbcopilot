from __future__ import annotations

from unittest.mock import AsyncMock

from app.models.metadata import GovernancePackage, RelationshipPackage
from app.services.kpi_intelligence_service import KPIIntelligenceService
from app.services.prompt_studio_service import PromptStudioService
from app.services.readiness_service import ReadinessService


def test_governance_package_failure_reason_alias() -> None:
    package = GovernancePackage()
    package.failure_reason = "missing context"

    assert package.raw_failure_reason == "missing context"
    assert package.failure_reason == "missing context"


def test_relationship_package_legacy_aliases() -> None:
    package = RelationshipPackage()
    package.entity_graph = [{"left": "a", "right": "b"}]
    package.lifecycle_flows = [{"name": "flow"}]

    assert package.business_entity_graph_alias == [{"left": "a", "right": "b"}]
    assert package.entity_lifecycle_descriptions_alias == [{"name": "flow"}]


def test_core_service_constructors_init() -> None:
    db = AsyncMock()

    PromptStudioService(db)
    KPIIntelligenceService(db)
    ReadinessService(db)
