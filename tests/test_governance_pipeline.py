from __future__ import annotations

import os
import sys
import logging

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.integration_ai_pipeline_utils import get_json, integration_enabled


logger = logging.getLogger(__name__)


@pytest.mark.integration
def test_governance_pipeline():
    if not integration_enabled():
        pytest.skip("Set RUN_AI_INTEGRATION_TESTS=1 to run live integration tests")

    ok, connections = get_json("/connections")
    assert ok, f"Failed to load connections: {connections}"
    target = next(
        (
            item
            for item in connections
            if "telehealth" in str(item.get("name", "")).lower()
            or "insurance" in str(item.get("name", "")).lower()
            or "telehealth" in str(item.get("display_name", "")).lower()
        ),
        None,
    )
    assert target is not None, f"Could not find telehealth sample connection in: {connections}"

    db_id = target["id"]
    ok, payload = get_json(f"/governance/packages/{db_id}", timeout=120)
    assert ok, f"Failed to fetch governance packages: {payload}"
    logger.info("governance package=%s", payload)

    packages = payload.get("packages", [])
    assert packages, "Expected governance packages to be persisted"
    flat_columns = [col for pkg in packages for col in pkg.get("pii_columns", [])]
    assert flat_columns, "Expected at least one PII column"

    all_text = str(payload).lower()
    assert "email" in all_text or any("email" in str(item).lower() for item in flat_columns), "email should be identified as PII"
    assert "phone" in all_text or any("phone" in str(item).lower() for item in flat_columns), "phone_number should be identified as PII"
    assert "aadhaar" in all_text or "aadhar" in all_text, "aadhaar_number should appear in governance output"
    assert "diagnosis" in all_text, "diagnosis_summary should appear in governance output"
