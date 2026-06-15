from __future__ import annotations

import os
import sys
import logging

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.ai_observability_service import AIObservabilityService, extract_azure_content
from tests.integration_ai_pipeline_utils import azure_configured, integration_enabled


logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_azure_connectivity():
    if not integration_enabled():
        pytest.skip("Set RUN_AI_INTEGRATION_TESTS=1 to run live Azure tests")
    if not azure_configured():
        pytest.skip("Azure OpenAI config is incomplete")

    service = AIObservabilityService()
    response = await service.generate(
        operation="chat",
        module="pii_governance",
        artifact_type="table_pii_classification",
        model_name="gpt-5-nano",
        messages=[
            {"role": "system", "content": "Return compact JSON only."},
            {
                "role": "user",
                "content": (
                    "Table: patients\n"
                    "Columns:\n"
                    "- email (varchar)\n"
                    "- phone_number (varchar)\n"
                    "Return:\n"
                    '{"resolved_columns":[]}'
                ),
            },
        ],
        request_kwargs={
            "response_format": {"type": "json_object"},
            "max_completion_tokens": 256,
            "reasoning_effort": "low",
        },
    )

    content = response.content or ""
    logger.info("azure_connectivity finish_reason=%s", response.token_usage.get("finish_reason") if isinstance(response.token_usage, dict) else None)
    logger.info("azure_connectivity token_usage=%s", response.token_usage)
    logger.info("azure_connectivity response_chars=%d", len(content))
    logger.info("azure_connectivity content=%s", content)

    assert content.strip(), f"Azure returned empty content: raw={response.raw_response!r}"
    assert extract_azure_content(response.raw_response) == content
    assert response.trace_id is not None
