from __future__ import annotations

import os
import sys
import logging

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.integration_ai_pipeline_utils import get_json, integration_enabled


logger = logging.getLogger(__name__)


@pytest.mark.integration
def test_relationship_pipeline():
    if not integration_enabled():
        pytest.skip("Set RUN_AI_INTEGRATION_TESTS=1 to run live integration tests")

    ok, connections = get_json("/connections")
    assert ok, f"Failed to load connections: {connections}"
    target = next((item for item in connections if item.get("status") == "active"), None)
    assert target is not None, "Expected at least one active connection"

    db_id = target["id"]
    ok, payload = get_json(f"/relationships/{db_id}", timeout=120)
    assert ok, f"Failed to fetch relationship package: {payload}"
    logger.info("relationship package=%s", payload)

    packages = payload.get("packages", [])
    assert packages, "Expected persisted relationship packages"
    assert any(pkg.get("entity_graph") for pkg in packages), "Expected entity graph output"
    assert any(pkg.get("cluster_summary") for pkg in packages), "Expected cluster summary output"
    assert any(pkg.get("domain_name") for pkg in packages), "Expected domain-scoped relationship intelligence"

    graph_ok, graph_payload = get_json(f"/relationships/graph/{db_id}", timeout=120)
    assert graph_ok, f"Failed to fetch relationship graph: {graph_payload}"
    logger.info("relationship graph=%s", graph_payload)
    edges = graph_payload.get("edges", [])
    assert edges, "Expected relationship graph edges to persist"
