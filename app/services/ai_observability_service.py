"""
Centralized AI observability wrapper for Azure OpenAI calls.

This service keeps Langfuse instrumentation lightweight and optional:
- If Langfuse is configured and installed, traces are emitted.
- If Langfuse is unavailable, the underlying AI call still runs normally.

The wrapper is intentionally framework-agnostic and does not introduce any
agent libraries or alternate LLM stacks.
"""

from __future__ import annotations

import asyncio
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
    from langfuse import Langfuse
except Exception:  # pragma: no cover - optional dependency.
    Langfuse = None


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
    """Lightweight wrapper around Azure OpenAI with optional Langfuse tracing."""

    _chat_client: Optional[Any] = None
    _embedding_client: Optional[Any] = None
    _langfuse: Optional[Any] = None

    def __init__(self) -> None:
        self._langfuse_client = self._get_langfuse_client()

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

    @classmethod
    def _get_langfuse_client(cls) -> Optional[Any]:
        """Return a cached Langfuse client when credentials are configured."""
        if cls._langfuse is not None:
            return cls._langfuse

        if Langfuse is None:
            return None

        if not (
            settings.langfuse_public_key
            and settings.langfuse_secret_key
            and settings.langfuse_host
        ):
            return None

        try:
            cls._langfuse = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
        except TypeError:
            cls._langfuse = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                base_url=settings.langfuse_host,
            )
        except Exception as exc:  # pragma: no cover - best-effort instrumentation.
            logger.warning("Langfuse initialization failed: %s", exc)
            cls._langfuse = None
            return None

        return cls._langfuse

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
        """Keep metadata compact and serializable for Langfuse."""
        cleaned: dict[str, Any] = {}
        for key, value in metadata.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                cleaned[key] = value
            else:
                cleaned[key] = str(value)
        return cleaned

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
        extra_metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        metadata = {
            "database_id": database_id,
            "database_name": database_name,
            "module": module,
            "artifact_type": artifact_type,
            "prompt_version": prompt_version,
            "model": model_name,
            "prompt_id": prompt_id,
            "completeness_score": completeness_score,
            "coverage_score": coverage_score,
            "confidence_score": confidence_score,
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
        extra_metadata: Optional[dict[str, Any]] = None,
    ) -> AIObservationResult:
        """Execute an Azure OpenAI call under an optional Langfuse trace."""
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
            extra_metadata=extra_metadata,
        )

        langfuse_client = self._langfuse_client
        trace_ctx = (
            langfuse_client.start_as_current_observation(
                name=self._trace_name(module, artifact_type, "trace"),
                as_type="span",
                input=trace_input,
                metadata=metadata,
                version=prompt_version,
            )
            if langfuse_client is not None
            else nullcontext()
        )

        start = time.perf_counter()
        try:
            with trace_ctx as trace:
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
                        langfuse_client=langfuse_client,
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
                    langfuse_client=langfuse_client,
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
        langfuse_client: Optional[Any],
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
            trace.start_as_current_generation(
                name=self._trace_name(module, artifact_type, "generation"),
                model=model_name,
                input=messages,
                metadata=metadata,
                version=prompt_version,
            )
            if trace is not None and hasattr(trace, "start_as_current_generation")
            else nullcontext()
        )

        with observation as generation:
            try:
                response = await asyncio.to_thread(_invoke)
                latency_ms = (time.perf_counter() - start) * 1000
                content = self._chat_content_from_response(response)
                usage = self._usage_from_response(response)
                if generation is not None:
                    generation.update(
                        output=content,
                        usage_details=usage,
                        metadata=metadata,
                        model=model_name,
                        version=prompt_version,
                    )

                if trace is not None:
                    trace.update(
                        output=content,
                        metadata=metadata,
                        version=prompt_version,
                    )

                trace_id = getattr(langfuse_client, "get_current_trace_id", lambda: None)()
                trace_url = getattr(langfuse_client, "get_trace_url", lambda trace_id=None: None)(trace_id=trace_id)

                return AIObservationResult(
                    operation="chat",
                    model_name=model_name,
                    prompt_id=prompt_id,
                    prompt_version=prompt_version,
                    latency_ms=latency_ms,
                    token_usage=usage,
                    content=content,
                    raw_response=response,
                    trace_id=trace_id,
                    trace_url=trace_url,
                    metadata=metadata,
                )
            except Exception as exc:
                if generation is not None:
                    generation.update(
                        output=None,
                        metadata={**metadata, "error": str(exc)},
                        model=model_name,
                        version=prompt_version,
                    )
                if trace is not None:
                    trace.update(
                        output=None,
                        metadata={**metadata, "error": str(exc)},
                        version=prompt_version,
                    )
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
        langfuse_client: Optional[Any],
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
            trace.start_as_current_observation(
                name=self._trace_name(module, artifact_type, "embedding"),
                as_type="embedding",
                input=input_texts,
                metadata=metadata,
                model=model_name,
                version=prompt_version,
            )
            if trace is not None and hasattr(trace, "start_as_current_observation")
            else nullcontext()
        )

        with observation as embedding_obs:
            try:
                response = await asyncio.to_thread(_invoke)
                latency_ms = (time.perf_counter() - start) * 1000
                vectors = self._embeddings_from_response(response)
                usage = self._usage_from_response(response)
                if embedding_obs is not None:
                    embedding_obs.update(
                        output=vectors,
                        usage_details=usage,
                        metadata=metadata,
                        model=model_name,
                        version=prompt_version,
                    )

                if trace is not None:
                    trace.update(
                        output={"vector_count": len(vectors), "model": model_name},
                        metadata=metadata,
                        version=prompt_version,
                    )

                trace_id = getattr(langfuse_client, "get_current_trace_id", lambda: None)()
                trace_url = getattr(langfuse_client, "get_trace_url", lambda trace_id=None: None)(trace_id=trace_id)

                return AIObservationResult(
                    operation="embeddings",
                    model_name=model_name,
                    prompt_id=prompt_id,
                    prompt_version=prompt_version,
                    latency_ms=latency_ms,
                    token_usage=usage,
                    embeddings=vectors,
                    raw_response=response,
                    trace_id=trace_id,
                    trace_url=trace_url,
                    metadata=metadata,
                )
            except Exception as exc:
                if embedding_obs is not None:
                    embedding_obs.update(
                        output=None,
                        metadata={**metadata, "error": str(exc)},
                        model=model_name,
                        version=prompt_version,
                    )
                if trace is not None:
                    trace.update(
                        output=None,
                        metadata={**metadata, "error": str(exc)},
                        version=prompt_version,
                    )
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
            extra_metadata=extra_metadata,
        )
        if self._langfuse_client is None:
            return nullcontext()
        return self._langfuse_client.start_as_current_observation(
            name=self._trace_name(module, artifact_type, "span"),
            as_type="span",
            input=metadata,
            metadata=metadata,
            version=prompt_version,
        )

    def flush(self) -> None:
        """Flush buffered Langfuse events when the SDK is available."""
        if self._langfuse_client is None:
            return
        try:
            self._langfuse_client.flush()
        except Exception as exc:  # pragma: no cover - best effort only.
            logger.debug("Langfuse flush failed: %s", exc)
