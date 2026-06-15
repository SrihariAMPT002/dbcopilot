from __future__ import annotations

import os
import sys
import logging

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.ai_observability_service import AIObservabilityService
from tests.integration_ai_pipeline_utils import azure_configured, integration_enabled


logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ai_observability_wrapper():
    if not integration_enabled():
        pytest.skip("Set RUN_AI_INTEGRATION_TESTS=1 to run live Azure tests")
    if not azure_configured():
        pytest.skip("Azure OpenAI config is incomplete")

    service = AIObservabilityService()
    result = await service.generate(
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

    logger.info("observability content_chars=%d", len(result.content or ""))
    logger.info("observability trace_id=%s", result.trace_id)
    logger.info("observability model_name=%s", result.model_name)
    logger.info("observability token_usage=%s", result.token_usage)
    if not result.content:
        logger.error("Full Azure response payload=%s", getattr(result.raw_response, "model_dump_json", lambda **_: str(result.raw_response))(indent=2) if hasattr(result.raw_response, "model_dump_json") else result.raw_response)

    assert result.content and result.content.strip(), "Expected non-empty Azure content"
    assert result.trace_id is not None
    assert result.model_name == "gpt-5-nano"
    assert isinstance(result.token_usage, dict) and result.token_usage
