from __future__ import annotations

from app.services.relationship_package_mapper import normalize_lifecycle_flows
from app.services.relationship_validator_service import RelationshipValidatorService


def test_normalize_lifecycle_flows_from_strings() -> None:
    flows = [
        "Onboarding: customer enters platform",
        "Engagement: usage metrics",
    ]

    normalized = normalize_lifecycle_flows(flows)

    assert normalized == [
        {
            "stage": "Onboarding",
            "description": "customer enters platform",
            "summary": "Onboarding: customer enters platform",
        },
        {
            "stage": "Engagement",
            "description": "usage metrics",
            "summary": "Engagement: usage metrics",
        },
    ]


def test_relationship_validator_normalizes_strings() -> None:
    validator = RelationshipValidatorService()
    payload = validator.parse_and_validate(
        """{
            "cluster_summary": "summary",
            "confidence_score": 0.8,
            "entity_graph": ["A -> B"],
            "lifecycle_flows": ["Onboarding: customer enters platform"]
        }"""
    )

    assert payload["entity_graph"] == [{"source": "A", "target": "B", "summary": "A -> B", "description": "B"}]
    assert payload["lifecycle_flows"] == [
        {
            "stage": "Onboarding",
            "description": "customer enters platform",
            "summary": "Onboarding: customer enters platform",
        }
    ]
