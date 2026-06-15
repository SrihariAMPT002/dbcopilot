from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.ai_observability_service import AIObservabilityService, extract_azure_content

def test_extract_azure_content_from_chat_completion_message():
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content='{"resolved_columns": []}'),
            )
        ]
    )
    assert extract_azure_content(response) == '{"resolved_columns": []}'


def test_extract_azure_content_from_output_text():
    response = SimpleNamespace(
        choices=[],
        output_text='{"cluster_summary": "Retail domain"}',
        output=None,
    )
    assert extract_azure_content(response) == '{"cluster_summary": "Retail domain"}'


def test_extract_azure_content_from_responses_output_items():
    response = SimpleNamespace(
        choices=[],
        output_text="",
        output=[
            {
                "type": "reasoning",
                "content": [{"type": "reasoning_text", "text": "thinking"}],
            },
            {
                "type": "message",
                "content": [{"type": "output_text", "text": '{"entity_graph": []}'}],
            },
        ],
    )
    assert extract_azure_content(response) == '{"entity_graph": []}'


def test_extract_azure_content_from_parsed_message_payload():
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content=None, parsed={"resolved_columns": []}),
            )
        ]
    )
    assert extract_azure_content(response) == '{"resolved_columns": []}'


def test_extract_azure_content_raises_for_empty_response():
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="length",
                message=SimpleNamespace(content=""),
            )
        ],
        output_text="",
        output=[{"type": "reasoning", "content": []}],
    )
    with pytest.raises(ValueError, match="azure_empty_response finish_reason=length"):
        extract_azure_content(response)


def test_generate_chat_retries_once_on_length(monkeypatch):
    service = AIObservabilityService()
    service._langsmith_enabled = False

    first = SimpleNamespace(
        choices=[SimpleNamespace(finish_reason="length", message=SimpleNamespace(content=""))],
        output_text="",
        output=[],
    )
    second = SimpleNamespace(
        choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content='{"resolved_columns": []}'))],
        output_text="",
        output=[],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=MagicMock(side_effect=[first, second]))))
    monkeypatch.setattr(AIObservabilityService, "_resolve_openai_client", classmethod(lambda cls, embedding=False: client))

    result = asyncio.run(
        service.generate(
            operation="chat",
            module="pii_governance",
            artifact_type="table_pii_classification",
            model_name="gpt-5-nano",
            messages=[{"role": "user", "content": "test"}],
            request_kwargs={"max_completion_tokens": 1200, "_retry_on_length": 1},
        )
    )

    assert result.content == '{"resolved_columns": []}'
    assert client.chat.completions.create.call_count == 2
