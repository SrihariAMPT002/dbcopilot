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

logger = logging.getLogger(__name__)

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
        return {
            "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
        }

    @staticmethod
    def _chat_content_from_response(response: Any) -> str:
        choices = getattr(response, "choices", []) or []
        if not choices:
            return ""
        message = getattr(choices[0], "message", None)
        return (getattr(message, "content", "") or "").strip()

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
                    metadata=metadata,
                    start=start,
                    trace_input=trace_input,
                    )
        except Exception:
            logger.exception(
                "AI observability wrapper failed | module=%s artifact_type=%s operation=%s",
                module,
                artifact_type,
                operation,
            )
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
        metadata: dict[str, Any],
        start: float,
        trace_input: dict[str, Any],
    ) -> AIObservationResult:
        client = self._resolve_openai_client(embedding=False)

        def _invoke() -> Any:
            kwargs: dict[str, Any] = {
                "model": model_name,
                "messages": messages,
            }
            kwargs.update(request_kwargs)
            return client.chat.completions.create(**kwargs)

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
                response = await asyncio.to_thread(_invoke)
                latency_ms = (time.perf_counter() - start) * 1000
                content = self._chat_content_from_response(response)
                usage = self._usage_from_response(response)
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
                    "AI chat complete | module=%s artifact_type=%s model=%s input_tokens_est=%d prompt_tokens=%d completion_tokens=%d total_tokens=%d output_chars=%d latency_ms=%.2f",
                    module,
                    artifact_type,
                    model_name,
                    estimated_input_tokens,
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                    usage.get("total_tokens", 0),
                    len(content),
                    latency_ms,
                )

                return AIObservationResult(
                    operation="chat",
                    model_name=model_name,
                    prompt_id=prompt_id,
                    prompt_version=prompt_version,
                    latency_ms=latency_ms,
                    token_usage=usage,
                    content=content,
                    raw_response=response,
                    trace_id=getattr(generation, "id", None),
                    trace_url=None,
                    metadata=metadata,
                )
            except Exception as exc:
                if generation is not None:
                    self._safe_trace_call(generation, "add_metadata", {**metadata, "error": str(exc)})
                    self._safe_trace_call(generation, "end", error=str(exc))
                logger.exception(
                    "Azure OpenAI chat generation failed | module=%s artifact_type=%s model=%s",
                    module,
                    artifact_type,
                    model_name,
                )
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
                response = await asyncio.to_thread(_invoke)
                latency_ms = (time.perf_counter() - start) * 1000
                vectors = self._embeddings_from_response(response)
                usage = self._usage_from_response(response)
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
                    token_usage=usage,
                    embeddings=vectors,
                    raw_response=response,
                    trace_id=getattr(embedding_obs, "id", None),
                    trace_url=None,
                    metadata=metadata,
                )
            except Exception as exc:
                if embedding_obs is not None:
                    self._safe_trace_call(embedding_obs, "add_metadata", {**metadata, "error": str(exc)})
                    self._safe_trace_call(embedding_obs, "end", error=str(exc))
                logger.exception(
                    "Azure OpenAI embeddings failed | module=%s artifact_type=%s model=%s",
                    module,
                    artifact_type,
                    model_name,
                )
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
