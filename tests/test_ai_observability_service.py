from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.ai_observability_service import extract_azure_content


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
