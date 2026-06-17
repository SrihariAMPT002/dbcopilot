"""
Centralized AI observability wrapper for Azure OpenAI calls.

This service keeps LangSmith instrumentation lightweight and optional:
- If LangSmith is configured and installed, traces are emitted.
- If LangSmith is unavailable, the underlying AI call still runs normally.

The wrapper is intentionally framework-agnostic and does not introduce any
agent libraries or alternate LLM stacks.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional, Sequence

from app.core.config import settings
from app.core.structured_logging import error_message
from app.config.prompts import get_prompt_registry

logger = logging.getLogger(__name__)


def _response_attr(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _stringify_message_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content") or ""
            else:
                text = _response_attr(item, "text") or _response_attr(item, "content") or ""
            if text:
                parts.append(str(text).strip())
        return "\n".join(parts).strip()
    return str(content).strip()


def _text_parts_from_output_content(content: Any) -> list[str]:
    if content is None:
        return []
    if isinstance(content, str):
        return [content.strip()] if content.strip() else []
    if not isinstance(content, list):
        return []
    parts: list[str] = []
    for item in content:
        item_type = _response_attr(item, "type", "")
        if item_type in {"output_text", "text"}:
            text = _response_attr(item, "text") or _response_attr(item, "content") or ""
            if text:
                parts.append(str(text).strip())
        elif isinstance(item, dict):
            text = item.get("text") or item.get("content") or ""
            if text:
                parts.append(str(text).strip())
        else:
            text = _response_attr(item, "text") or _response_attr(item, "content") or ""
            if text:
                parts.append(str(text).strip())
    return parts


def _content_from_output_items(output: Any) -> str:
    if output is None:
        return ""
    if isinstance(output, str):
        return output.strip()
    if not isinstance(output, list):
        return ""
    parts: list[str] = []
    for item in output:
        item_type = _response_attr(item, "type", "")
        if item_type in {"message", "output_message", "assistant"}:
            parts.extend(_text_parts_from_output_content(_response_attr(item, "content")))
        elif item_type in {"output_text", "text"}:
            text = _response_attr(item, "text") or _response_attr(item, "content") or ""
            if text:
                parts.append(str(text).strip())
        elif isinstance(item, dict):
            if item.get("type") in {"message", "output_message", "assistant"}:
                parts.extend(_text_parts_from_output_content(item.get("content")))
            else:
                text = item.get("text") or item.get("content") or ""
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
    return "\n".join(parts).strip()


def _content_from_choices(response: Any) -> str:
    choices = _response_attr(response, "choices", []) or []
    if not choices:
        return ""
    choice = choices[0]
    message = _response_attr(choice, "message")
    if message is None:
        return ""
    content = _stringify_message_content(_response_attr(message, "content"))
    if content:
        return content
    parsed = _response_attr(message, "parsed")
    if parsed is not None:
        if isinstance(parsed, dict):
            return json.dumps(parsed)
        return str(parsed).strip()
    return ""


def _resolve_finish_reason(response: Any) -> str:
    choices = _response_attr(response, "choices", []) or []
    if choices:
        finish_reason = _response_attr(choices[0], "finish_reason")
        if finish_reason:
            return str(finish_reason)
    status = _response_attr(response, "status")
    if status:
        return str(status)
    incomplete = _response_attr(response, "incomplete_details")
    if incomplete is not None:
        reason = _response_attr(incomplete, "reason")
        if reason:
            return str(reason)
    return "unknown"


def extract_azure_content(response: Any) -> str:
    """Extract assistant text from Azure OpenAI chat or responses-shaped payloads."""
    content = _content_from_choices(response)
    if content:
        return content

    output_text = _response_attr(response, "output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    content = _content_from_output_items(_response_attr(response, "output"))
    if content:
        return content

    finish_reason = _resolve_finish_reason(response)
    raise ValueError(f"azure_empty_response finish_reason={finish_reason}")


def _serialize_for_log(value: Any) -> str:
    if value is None:
        return "null"
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return json.dumps(model_dump(), default=str)
        except Exception:
            pass
    try:
        return json.dumps(value, default=str)
    except Exception:
        return repr(value)


def _response_dump_json(response: Any) -> str:
    dump_json = getattr(response, "model_dump_json", None)
    if callable(dump_json):
        try:
            return dump_json(indent=2)
        except TypeError:
            try:
                return dump_json()
            except Exception:
                pass
        except Exception:
            pass
    return _serialize_for_log(response)


try:  # Optional dependency.
    from openai import AzureOpenAI
except Exception:  # pragma: no cover - optional dependency.
    AzureOpenAI = None

try:  # Optional dependency.
    from langsmith.run_helpers import trace as langsmith_trace
    from langsmith.run_helpers import tracing_context as langsmith_tracing_context
except Exception:  # pragma: no cover - optional dependency.
    langsmith_trace = None
    langsmith_tracing_context = None


OperationType = Literal["chat", "embeddings"]


@dataclass
class AIObservationResult:
    """Normalized result from an instrumented AI call."""

    operation: OperationType
    model_name: str
    prompt_id: Optional[str] = None
    prompt_version: Optional[str] = None
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    latency_ms: float = 0.0
    estimated_input_tokens: int = 0
    actual_input_tokens: int = 0
    estimated_output_tokens: int = 0
    actual_output_tokens: int = 0
    prompt_size_bytes: int = 0
    completion_truncated: bool = False
    token_usage: dict[str, int] = field(default_factory=dict)
    content: Optional[str] = None
    embeddings: Optional[list[list[float]]] = None
    raw_response: Any = None
    trace_id: Optional[str] = None
    trace_url: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AIObservabilityService:
    """Lightweight wrapper around Azure OpenAI with optional LangSmith tracing."""

    _chat_client: Optional[Any] = None
    _embedding_client: Optional[Any] = None

    def __init__(self) -> None:
        self._langsmith_enabled = bool(settings.langsmith_tracing and langsmith_trace is not None)
        self._prompt_registry = None

    @staticmethod
    def _dev_logging_enabled() -> bool:
        return bool(getattr(settings, "is_development", False) or getattr(settings, "debug", False))

    @classmethod
    def _resolve_openai_client(
        cls,
        *,
        embedding: bool = False,
    ) -> Any:
        """Return a cached Azure OpenAI client for chat or embeddings."""
        client_attr = "_embedding_client" if embedding else "_chat_client"
        cached = getattr(cls, client_attr)
        if cached is not None:
            return cached

        if AzureOpenAI is None:
            raise ImportError("openai package is required for Azure OpenAI calls")

        if embedding:
            endpoint = settings.azure_openai_embedding_url or settings.azure_openai_endpoint
            key = settings.azure_openai_embedding_api_key or settings.azure_openai_key
            deployment = settings.azure_openai_embedding_deployment
        else:
            endpoint = settings.azure_openai_endpoint
            key = settings.azure_openai_key
            deployment = settings.azure_openai_deployment

        if not endpoint or not key:
            scope = "embedding" if embedding else "chat"
            raise ValueError(f"Azure OpenAI {scope} credentials are not configured")

        client = AzureOpenAI(
            api_key=key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=endpoint,
        )
        setattr(cls, client_attr, client)
        logger.debug("Initialized Azure OpenAI %s client for deployment %s", "embedding" if embedding else "chat", deployment)
        return client

    @staticmethod
    def _usage_from_response(response: Any) -> dict[str, int]:
        usage = getattr(response, "usage", None)
        if not usage:
            return {}
        completion_tokens_details = getattr(usage, "completion_tokens_details", None)
        reasoning_tokens = 0
        if completion_tokens_details is not None:
            reasoning_tokens = int(getattr(completion_tokens_details, "reasoning_tokens", 0) or 0)
        return {
            "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
            "reasoning_tokens": reasoning_tokens,
        }

    @staticmethod
    def _response_usage_summary(response: Any) -> dict[str, Any]:
        usage = AIObservabilityService._usage_from_response(response)
        return {
            "finish_reason": _resolve_finish_reason(response),
            "model": _response_attr(response, "model"),
            "deployment": _response_attr(response, "deployment") or _response_attr(response, "model"),
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "reasoning_tokens": usage.get("reasoning_tokens", 0),
        }

    @staticmethod
    def _response_content_length(response: Any) -> int:
        try:
            content = extract_azure_content(response)
        except Exception:
            content = _content_from_choices(response) or _response_attr(response, "output_text") or _content_from_output_items(_response_attr(response, "output"))
        return len(content or "")

    @staticmethod
    def _request_budget_summary(request_payload: dict[str, Any], *, operation: OperationType) -> dict[str, Any]:
        if operation == "embeddings":
            texts = request_payload.get("input", []) or []
            prompt_text = json.dumps(texts, default=str)
            completion_budget = 0
        else:
            messages = request_payload.get("messages", []) or []
            prompt_text = json.dumps(messages, default=str)
            completion_budget = int(request_payload.get("max_completion_tokens") or request_payload.get("max_tokens") or 0)
        return {
            "prompt_chars": len(prompt_text),
            "prompt_tokens_est": AIObservabilityService._estimate_text_tokens(prompt_text),
            "completion_budget": completion_budget,
            "request_chars": len(_serialize_for_log(request_payload)),
        }

    @staticmethod
    def _resolve_completion_budget(prompt_tokens_est: int, requested_completion_budget: int) -> tuple[int, int]:
        estimated_tokens = prompt_tokens_est + max(requested_completion_budget, 4000)
        dynamic_budget = int(min(max(4000, estimated_tokens * 0.35), 16000))
        return estimated_tokens, max(requested_completion_budget, dynamic_budget)

    def _prompt_completion_budget(self, prompt_id: Optional[str]) -> int | None:
        if not prompt_id:
            return None
        if self._prompt_registry is None:
            self._prompt_registry = get_prompt_registry()
        try:
            for prompt_path in self._prompt_registry.list_prompts():
                category, current_id = prompt_path.split("/", 1) if "/" in prompt_path else ("", prompt_path)
                if current_id != prompt_id:
                    continue
                prompt = self._prompt_registry.load_prompt(current_id, category=category or None)
                constraints = prompt.get("constraints", {}) if isinstance(prompt, dict) else {}
                budget = constraints.get("max_completion_tokens") or constraints.get("max_tokens")
                if budget is not None:
                    return int(budget)
        except Exception:
            logger.debug("Unable to resolve prompt budget for %s", prompt_id, exc_info=True)
        return None

    @staticmethod
    def _embeddings_from_response(response: Any) -> list[list[float]]:
        data = getattr(response, "data", []) or []
        return [list(item.embedding) for item in data if getattr(item, "embedding", None) is not None]

    @staticmethod
    def _trace_name(module: str, artifact_type: str, operation: OperationType) -> str:
        return f"{module}.{artifact_type}.{operation}"

    @staticmethod
    def _sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        """Keep metadata compact and serializable for LangSmith."""
        cleaned: dict[str, Any] = {}
        for key, value in metadata.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                cleaned[key] = value
            else:
                cleaned[key] = str(value)
        return cleaned

    @staticmethod
    def _estimate_text_tokens(text: str) -> int:
        # Rough fallback when tokenizer metadata is not available.
        if not text:
            return 0
        return max(1, int(len(text) / 4))

    @classmethod
    def _estimate_message_tokens(cls, messages: list[dict[str, Any]]) -> int:
        total = 0
        for message in messages:
            total += cls._estimate_text_tokens(str(message.get("role", "")))
            content = message.get("content", "")
            if isinstance(content, str):
                total += cls._estimate_text_tokens(content)
            else:
                total += cls._estimate_text_tokens(json.dumps(content, default=str))
        return total

    @classmethod
    def _estimate_input_tokens(cls, operation: OperationType, trace_input: dict[str, Any]) -> int:
        if operation == "embeddings":
            texts = trace_input.get("texts") or []
            return sum(cls._estimate_text_tokens(str(text)) for text in texts)
        messages = trace_input.get("messages") or []
        return cls._estimate_message_tokens(messages)

    @staticmethod
    def _safe_trace_call(trace_obj: Any, method_name: str, *args: Any, **kwargs: Any) -> None:
        if trace_obj is None:
            return
        try:
            method = getattr(trace_obj, method_name, None)
            if callable(method):
                method(*args, **kwargs)
        except Exception:
            logger.debug("LangSmith trace call failed: %s", method_name, exc_info=True)

    def _build_trace_metadata(
        self,
        *,
        module: str,
        artifact_type: str,
        database_id: Optional[int],
        database_name: Optional[str],
        prompt_id: Optional[str],
        prompt_version: Optional[str],
        model_name: str,
        completeness_score: Optional[float],
        coverage_score: Optional[float],
        confidence_score: Optional[float],
        execution_status: Optional[str] = None,
        retry_count: Optional[int] = None,
        fallback_used: Optional[bool] = None,
        extra_metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        metadata = {
            "database_id": database_id,
            "database_name": database_name,
            "module": module,
            "artifact_type": artifact_type,
            "feature": (extra_metadata or {}).get("feature", module),
            "prompt_name": prompt_id,
            "prompt_version": prompt_version,
            "model": model_name,
            "prompt_id": prompt_id,
            "completeness_score": completeness_score,
            "coverage_score": coverage_score,
            "confidence_score": confidence_score,
            "execution_status": execution_status,
            "retry_count": retry_count,
            "fallback_used": fallback_used,
        }
        if extra_metadata:
            metadata.update(extra_metadata)
        return self._sanitize_metadata(metadata)

    async def generate(
        self,
        *,
        operation: OperationType,
        module: str,
        artifact_type: str,
        prompt_id: Optional[str] = None,
        prompt_version: Optional[str] = None,
        database_id: Optional[int] = None,
        database_name: Optional[str] = None,
        model_name: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        input_texts: Optional[Sequence[str]] = None,
        request_kwargs: Optional[dict[str, Any]] = None,
        completeness_score: Optional[float] = None,
        coverage_score: Optional[float] = None,
        confidence_score: Optional[float] = None,
        execution_status: Optional[str] = None,
        retry_count: Optional[int] = None,
        fallback_used: Optional[bool] = None,
        extra_metadata: Optional[dict[str, Any]] = None,
    ) -> AIObservationResult:
        """Execute an Azure OpenAI call under an optional LangSmith trace."""
        request_kwargs = dict(request_kwargs or {})
        retry_on_length = int(request_kwargs.pop("_retry_on_length", 0) or 0)
        prompt_budget = self._prompt_completion_budget(prompt_id)
        if prompt_budget is not None:
            current_budget = int(request_kwargs.get("max_completion_tokens") or request_kwargs.get("max_tokens") or 0)
            if current_budget < prompt_budget:
                request_kwargs["max_completion_tokens"] = prompt_budget
                request_kwargs.pop("max_tokens", None)
        model = model_name or (
            settings.azure_openai_embedding_deployment if operation == "embeddings" else settings.azure_openai_deployment
        )
        trace_input: dict[str, Any]
        if operation == "embeddings":
            trace_input = {
                "texts": list(input_texts or []),
                "request_kwargs": request_kwargs,
            }
        else:
            trace_input = {
                "messages": messages or [],
                "request_kwargs": request_kwargs,
            }

        metadata = self._build_trace_metadata(
            module=module,
            artifact_type=artifact_type,
            database_id=database_id,
            database_name=database_name,
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            model_name=model,
            completeness_score=completeness_score,
            coverage_score=coverage_score,
            confidence_score=confidence_score,
            execution_status=execution_status,
            retry_count=retry_count,
            fallback_used=fallback_used,
            extra_metadata=extra_metadata,
        )

        trace_ctx = (
            langsmith_tracing_context(
                project_name=settings.langsmith_project,
                metadata=metadata,
                enabled=True,
            )
            if self._langsmith_enabled and langsmith_tracing_context is not None
            else nullcontext()
        )

        start = time.perf_counter()
        try:
            with trace_ctx as trace:
                self._safe_trace_call(trace, "add_inputs", trace_input)
                if operation == "embeddings":
                    return await self._generate_embeddings(
                        trace=trace,
                        module=module,
                        artifact_type=artifact_type,
                        prompt_id=prompt_id,
                        prompt_version=prompt_version,
                        database_id=database_id,
                        database_name=database_name,
                        model_name=model,
                        input_texts=list(input_texts or []),
                        request_kwargs=request_kwargs,
                        metadata=metadata,
                        start=start,
                        trace_input=trace_input,
                        )

                return await self._generate_chat(
                    trace=trace,
                    module=module,
                    artifact_type=artifact_type,
                    prompt_id=prompt_id,
                    prompt_version=prompt_version,
                    database_id=database_id,
                    database_name=database_name,
                    model_name=model,
                    messages=list(messages or []),
                    request_kwargs=request_kwargs,
                    retry_on_length=retry_on_length,
                    metadata=metadata,
                    start=start,
                    trace_input=trace_input,
                    )
        except Exception as exc:
            logger.exception(error_message("ai observability wrapper failed", module=module, artifact_type=artifact_type, operation=operation, reason=exc))
            raise

    async def _generate_chat(
        self,
        *,
        trace: Any,
        module: str,
        artifact_type: str,
        prompt_id: Optional[str],
        prompt_version: Optional[str],
        database_id: Optional[int],
        database_name: Optional[str],
        model_name: str,
        messages: list[dict[str, Any]],
        request_kwargs: dict[str, Any],
        retry_on_length: int,
        metadata: dict[str, Any],
        start: float,
        trace_input: dict[str, Any],
    ) -> AIObservationResult:
        client = self._resolve_openai_client(embedding=False)

        def _invoke(request_payload: dict[str, Any]) -> Any:
            return client.chat.completions.create(**request_payload)

        request_payload: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
        }
        request_payload.update(request_kwargs)
        if str(model_name).startswith("gpt-5") and "reasoning_effort" not in request_payload:
            request_payload["reasoning_effort"] = "low"

        dev_logging = self._dev_logging_enabled()
        if dev_logging:
            logger.info(
                "AI dev request | module=%s artifact_type=%s model=%s prompt_id=%s prompt_version=%s metadata=%s input=%s request_kwargs=%s",
                module,
                artifact_type,
                model_name,
                prompt_id,
                prompt_version,
                _serialize_for_log(metadata),
                _serialize_for_log(trace_input),
                _serialize_for_log(request_kwargs),
            )

        observation = (
            langsmith_trace(
                name=self._trace_name(module, artifact_type, "generation"),
                run_type="llm",
                inputs=trace_input,
                metadata=metadata,
                project_name=settings.langsmith_project,
            )
            if self._langsmith_enabled and langsmith_trace is not None
            else nullcontext()
        )

        with observation as generation:
            try:
                budget_summary = self._request_budget_summary(request_payload, operation="chat")
                _estimated_tokens, dynamic_completion_budget = self._resolve_completion_budget(
                    budget_summary["prompt_tokens_est"],
                    int(budget_summary["completion_budget"] or 0),
                )
                request_payload["max_completion_tokens"] = dynamic_completion_budget
                request_payload.pop("max_tokens", None)
                logger.info(
                    "AI preflight | module=%s artifact_type=%s model=%s prompt_chars=%d prompt_tokens_est=%d completion_budget=%d request_chars=%d",
                    module,
                    artifact_type,
                    model_name,
                    budget_summary["prompt_chars"],
                    budget_summary["prompt_tokens_est"],
                    dynamic_completion_budget,
                    budget_summary["request_chars"],
                )
                logger.error("AZURE REQUEST=%s", _serialize_for_log(request_payload))
                logger.error(
                    "AZURE REQUEST SIZE | module=%s artifact_type=%s prompt_chars=%d prompt_tokens_est=%d completion_budget=%d request_chars=%d",
                    module,
                    artifact_type,
                    budget_summary["prompt_chars"],
                    budget_summary["prompt_tokens_est"],
                    budget_summary["completion_budget"],
                    budget_summary["request_chars"],
                )
                response = await asyncio.to_thread(_invoke, request_payload)
                raw_response_dump = _response_dump_json(response)
                logger.error("AZURE RAW RESPONSE=%s", raw_response_dump)
                logger.error("AZURE RESPONSE DUMP=%s", _serialize_for_log(response))
                response_summary = self._response_usage_summary(response)
                logger.info(
                    "AZURE RESPONSE META | module=%s artifact_type=%s finish_reason=%s prompt_tokens=%d completion_tokens=%d total_tokens=%d reasoning_tokens=%d response_chars=%d",
                    module,
                    artifact_type,
                    response_summary["finish_reason"],
                    response_summary["prompt_tokens"],
                    response_summary["completion_tokens"],
                    response_summary["total_tokens"],
                    response_summary["reasoning_tokens"],
                    len(raw_response_dump),
                )
                try:
                    content = extract_azure_content(response)
                except ValueError as exc:
                    finish_reason = _resolve_finish_reason(response)
                    if retry_on_length > 0 and finish_reason == "length":
                        retry_on_length -= 1
                        retry_budget = int(min(max(dynamic_completion_budget + 1000, dynamic_completion_budget * 1.5), 16000))
                        request_payload["max_completion_tokens"] = retry_budget
                        logger.warning(
                            "Azure OpenAI truncation retry | module=%s artifact_type=%s model=%s retry_budget=%d remaining_retries=%d",
                            module,
                            artifact_type,
                            model_name,
                            retry_budget,
                            retry_on_length,
                        )
                        response = await asyncio.to_thread(_invoke, request_payload)
                        raw_response_dump = _response_dump_json(response)
                        response_summary = self._response_usage_summary(response)
                        try:
                            content = extract_azure_content(response)
                        except ValueError:
                            finish_reason = _resolve_finish_reason(response)
                            logger.warning(
                                "Azure OpenAI extraction failed after retry | module=%s artifact_type=%s model=%s finish_reason=%s prompt_chars=%d response_chars=%d",
                                module,
                                artifact_type,
                                model_name,
                                finish_reason,
                                len(_serialize_for_log(request_payload)),
                                len(raw_response_dump),
                            )
                            raise
                    else:
                        logger.warning(
                            "Azure OpenAI extraction failed | module=%s artifact_type=%s model=%s finish_reason=%s prompt_chars=%d response_chars=%d",
                            module,
                            artifact_type,
                            model_name,
                            finish_reason,
                            len(_serialize_for_log(request_payload)),
                            len(raw_response_dump),
                        )
                        raise
                logger.error("EXTRACTED CONTENT=%s", content)
                latency_ms = (time.perf_counter() - start) * 1000
                usage = self._usage_from_response(response)
                summary = self._response_usage_summary(response)
                actual_input_tokens = int(usage.get("prompt_tokens", 0) or 0)
                actual_output_tokens = int(usage.get("completion_tokens", 0) or 0)
                completion_truncated = summary["finish_reason"] == "length" or (
                    dynamic_completion_budget > 0
                    and actual_output_tokens >= int(dynamic_completion_budget * 0.9)
                )
                logger.info(
                    "AI request usage | module=%s artifact_type=%s model=%s deployment=%s finish_reason=%s prompt_tokens=%d completion_tokens=%d total_tokens=%d reasoning_tokens=%d",
                    module,
                    artifact_type,
                    summary["model"],
                    summary["deployment"],
                    summary["finish_reason"],
                    summary["prompt_tokens"],
                    summary["completion_tokens"],
                    summary["total_tokens"],
                    summary["reasoning_tokens"],
                )
                if dev_logging:
                    logger.info(
                        "AI dev result | module=%s artifact_type=%s model=%s latency_ms=%.2f usage=%s content=%s",
                        module,
                        artifact_type,
                        model_name,
                        latency_ms,
                        _serialize_for_log(usage),
                        content,
                    )
                if generation is not None:
                    self._safe_trace_call(generation, "add_outputs", {"content": content})
                    self._safe_trace_call(
                        generation,
                        "add_metadata",
                        {**metadata, "token_usage": usage, "latency_ms": latency_ms},
                    )
                    self._safe_trace_call(generation, "end", outputs={"content": content})

                estimated_input_tokens = self._estimate_input_tokens("chat", trace_input)
                logger.info(
                    "AI chat complete | module=%s artifact_type=%s model=%s input_tokens_est=%d prompt_tokens=%d completion_tokens=%d total_tokens=%d reasoning_tokens=%d output_chars=%d latency_ms=%.2f",
                    module,
                    artifact_type,
                    model_name,
                    estimated_input_tokens,
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                    usage.get("total_tokens", 0),
                    usage.get("reasoning_tokens", 0),
                    len(content),
                    latency_ms,
                )

                return AIObservationResult(
                    operation="chat",
                    model_name=model_name,
                    prompt_id=prompt_id,
                    prompt_version=prompt_version,
                    latency_ms=latency_ms,
                    estimated_input_tokens=estimated_input_tokens,
                    actual_input_tokens=actual_input_tokens,
                    estimated_output_tokens=dynamic_completion_budget,
                    actual_output_tokens=actual_output_tokens,
                    prompt_size_bytes=len(_serialize_for_log(request_payload)),
                    completion_truncated=completion_truncated,
                    token_usage=usage,
                    content=content,
                    raw_response=response,
                    trace_id=str(getattr(generation, "id", None)) if getattr(generation, "id", None) is not None else None,
                    trace_url=None,
                    metadata={
                        **metadata,
                        "estimated_input_tokens": estimated_input_tokens,
                        "actual_input_tokens": actual_input_tokens,
                        "estimated_output_tokens": dynamic_completion_budget,
                        "actual_output_tokens": actual_output_tokens,
                        "prompt_size_bytes": len(_serialize_for_log(request_payload)),
                        "completion_truncated": completion_truncated,
                        "finish_reason": summary["finish_reason"],
                    },
                )
            except Exception as exc:
                if generation is not None:
                    self._safe_trace_call(generation, "add_metadata", {**metadata, "error": str(exc)})
                    self._safe_trace_call(generation, "end", error=str(exc))
                logger.exception(error_message("azure openai chat generation failed", module=module, artifact_type=artifact_type, model=model_name, reason=exc))
                raise

    async def _generate_embeddings(
        self,
        *,
        trace: Any,
        module: str,
        artifact_type: str,
        prompt_id: Optional[str],
        prompt_version: Optional[str],
        database_id: Optional[int],
        database_name: Optional[str],
        model_name: str,
        input_texts: list[str],
        request_kwargs: dict[str, Any],
        metadata: dict[str, Any],
        start: float,
        trace_input: dict[str, Any],
    ) -> AIObservationResult:
        client = self._resolve_openai_client(embedding=True)

        def _invoke() -> Any:
            kwargs: dict[str, Any] = {
                "model": model_name,
                "input": input_texts,
            }
            kwargs.update(request_kwargs)
            return client.embeddings.create(**kwargs)

        observation = (
            langsmith_trace(
                name=self._trace_name(module, artifact_type, "embedding"),
                run_type="llm",
                inputs=trace_input,
                metadata=metadata,
                project_name=settings.langsmith_project,
            )
            if self._langsmith_enabled and langsmith_trace is not None
            else nullcontext()
        )

        with observation as embedding_obs:
            try:
                budget_summary = self._request_budget_summary({"input": input_texts, **request_kwargs}, operation="embeddings")
                _estimated_tokens, dynamic_completion_budget = self._resolve_completion_budget(
                    budget_summary["prompt_tokens_est"],
                    int(budget_summary["completion_budget"] or 0),
                )
                request_kwargs = dict(request_kwargs)
                request_kwargs.pop("max_tokens", None)
                logger.info(
                    "AI preflight | module=%s artifact_type=%s model=%s prompt_chars=%d prompt_tokens_est=%d completion_budget=%d request_chars=%d",
                    module,
                    artifact_type,
                    model_name,
                    budget_summary["prompt_chars"],
                    budget_summary["prompt_tokens_est"],
                    dynamic_completion_budget,
                    budget_summary["request_chars"],
                )
                response = await asyncio.to_thread(_invoke)
                latency_ms = (time.perf_counter() - start) * 1000
                vectors = self._embeddings_from_response(response)
                usage = self._usage_from_response(response)
                actual_input_tokens = int(usage.get("prompt_tokens", 0) or 0)
                if embedding_obs is not None:
                    self._safe_trace_call(embedding_obs, "add_outputs", {"vector_count": len(vectors)})
                    self._safe_trace_call(
                        embedding_obs,
                        "add_metadata",
                        {**metadata, "token_usage": usage, "latency_ms": latency_ms},
                    )
                    self._safe_trace_call(embedding_obs, "end", outputs={"vector_count": len(vectors)})

                estimated_input_tokens = self._estimate_input_tokens("embeddings", trace_input)
                logger.info(
                    "AI embeddings complete | module=%s artifact_type=%s model=%s input_tokens_est=%d prompt_tokens=%d completion_tokens=%d total_tokens=%d vectors=%d latency_ms=%.2f",
                    module,
                    artifact_type,
                    model_name,
                    estimated_input_tokens,
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                    usage.get("total_tokens", 0),
                    len(vectors),
                    latency_ms,
                )

                return AIObservationResult(
                    operation="embeddings",
                    model_name=model_name,
                    prompt_id=prompt_id,
                    prompt_version=prompt_version,
                    latency_ms=latency_ms,
                    estimated_input_tokens=estimated_input_tokens,
                    actual_input_tokens=actual_input_tokens,
                    estimated_output_tokens=dynamic_completion_budget,
                    actual_output_tokens=int(usage.get("completion_tokens", 0) or 0),
                    prompt_size_bytes=len(_serialize_for_log({"input": input_texts, **request_kwargs})),
                    completion_truncated=False,
                    token_usage=usage,
                    embeddings=vectors,
                    raw_response=response,
                    trace_id=str(getattr(embedding_obs, "id", None)) if getattr(embedding_obs, "id", None) is not None else None,
                    trace_url=None,
                    metadata={
                        **metadata,
                        "estimated_input_tokens": estimated_input_tokens,
                        "actual_input_tokens": actual_input_tokens,
                        "estimated_output_tokens": dynamic_completion_budget,
                        "actual_output_tokens": int(usage.get("completion_tokens", 0) or 0),
                        "prompt_size_bytes": len(_serialize_for_log({"input": input_texts, **request_kwargs})),
                        "completion_truncated": False,
                        "finish_reason": _resolve_finish_reason(response),
                    },
                )
            except Exception as exc:
                if embedding_obs is not None:
                    self._safe_trace_call(embedding_obs, "add_metadata", {**metadata, "error": str(exc)})
                    self._safe_trace_call(embedding_obs, "end", error=str(exc))
                logger.exception(error_message("azure openai embeddings failed", module=module, artifact_type=artifact_type, model=model_name, reason=exc))
                raise

    def observe(
        self,
        *,
        module: str,
        artifact_type: str,
        prompt_id: Optional[str] = None,
        prompt_version: Optional[str] = None,
        database_id: Optional[int] = None,
        database_name: Optional[str] = None,
        model_name: Optional[str] = None,
        completeness_score: Optional[float] = None,
        coverage_score: Optional[float] = None,
        confidence_score: Optional[float] = None,
        execution_status: Optional[str] = None,
        retry_count: Optional[int] = None,
        fallback_used: Optional[bool] = None,
        extra_metadata: Optional[dict[str, Any]] = None,
    ):
        """Return a trace/span context manager for non-LLM operations."""
        metadata = self._build_trace_metadata(
            module=module,
            artifact_type=artifact_type,
            database_id=database_id,
            database_name=database_name,
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            model_name=model_name or "n/a",
            completeness_score=completeness_score,
            coverage_score=coverage_score,
            confidence_score=confidence_score,
            execution_status=execution_status,
            retry_count=retry_count,
            fallback_used=fallback_used,
            extra_metadata=extra_metadata,
        )
        if not self._langsmith_enabled or langsmith_trace is None:
            return nullcontext()
        return langsmith_trace(
            name=self._trace_name(module, artifact_type, "span"),
            run_type="chain",
            inputs=metadata,
            metadata=metadata,
            project_name=settings.langsmith_project,
        )

    def flush(self) -> None:
        """Flush is a no-op for LangSmith in this wrapper."""
        return
