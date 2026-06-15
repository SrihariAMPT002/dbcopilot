from __future__ import annotations

import os
import sys
import logging

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.integration_ai_pipeline_utils import get_json, integration_enabled


logger = logging.getLogger(__name__)


@pytest.mark.integration
def test_semantic_pipeline():
    if not integration_enabled():
        pytest.skip("Set RUN_AI_INTEGRATION_TESTS=1 to run live integration tests")

    ok, connections = get_json("/connections")
    assert ok, f"Failed to load connections: {connections}"
    target = next((item for item in connections if item.get("status") == "active"), None)
    assert target is not None, "Expected at least one active connection"

    db_id = target["id"]
    ok, payload = get_json(f"/semantics/{db_id}", timeout=120)
    assert ok, f"Failed to fetch semantic profile: {payload}"
    logger.info("semantic profile=%s", payload)

    assert payload.get("business_domain"), "business_domain should be populated"
    assert payload.get("business_entities"), "business_entities should be populated"
    assert payload.get("business_summary") or payload.get("semantic_summary"), "semantic_summary should be populated"
    logger.info("semantic prompt_size=%d response_size=%d", 0, len(str(payload)))
