from __future__ import annotations

import os
import sys
import logging

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.integration_ai_pipeline_utils import get_json, integration_enabled, post_json


logger = logging.getLogger(__name__)


@pytest.mark.integration
def test_end_to_end_sync():
    if not integration_enabled():
        pytest.skip("Set RUN_AI_INTEGRATION_TESTS=1 to run live integration tests")

    ok, connections = get_json("/connections")
    assert ok, f"Failed to load connections: {connections}"
    target = next((item for item in connections if item.get("status") == "active"), None)
    assert target is not None, "Expected at least one active connection"

    db_id = target["id"]
    ok, sync_response = post_json(f"/connections/{db_id}/sync", {}, timeout=600)
    assert ok, f"Sync failed: {sync_response}"
    logger.info("sync response=%s", sync_response)

    ok, semantic_payload = get_json(f"/semantics/{db_id}", timeout=120)
    assert ok, f"Semantic fetch failed: {semantic_payload}"
    ok, governance_payload = get_json(f"/governance/packages/{db_id}", timeout=120)
    assert ok, f"Governance fetch failed: {governance_payload}"
    ok, relationship_payload = get_json(f"/relationships/{db_id}", timeout=120)
    assert ok, f"Relationship fetch failed: {relationship_payload}"

    logger.info("semantic=%s", semantic_payload)
    logger.info("governance=%s", governance_payload)
    logger.info("relationship=%s", relationship_payload)

    assert semantic_payload, "Expected semantic intelligence to persist"
    assert governance_payload.get("packages"), "Expected governance intelligence to persist"
    assert relationship_payload.get("packages"), "Expected relationship intelligence to persist"
