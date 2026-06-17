"""Typed context contracts for pipeline stage propagation."""

from __future__ import annotations

from dataclasses import dataclass, field
from dataclasses import asdict
from typing import Any, Optional


@dataclass(slots=True)
class GovernanceContext:
    packages: list[dict[str, Any]] = field(default_factory=list)
    package_version: Optional[str] = None
    generated_at: Optional[str] = None
    pipeline_execution_id: Optional[int] = None


@dataclass(slots=True)
class SemanticContext:
    package: dict[str, Any] | None = None
    package_version: Optional[str] = None
    generated_at: Optional[str] = None
    pipeline_execution_id: Optional[int] = None


@dataclass(slots=True)
class RelationshipContext:
    packages: list[dict[str, Any]] = field(default_factory=list)
    package_version: Optional[str] = None
    generated_at: Optional[str] = None
    pipeline_execution_id: Optional[int] = None


@dataclass(slots=True)
class KPIContext:
    package: dict[str, Any] | None = None
    catalog: list[dict[str, Any]] = field(default_factory=list)
    package_version: Optional[str] = None
    generated_at: Optional[str] = None
    pipeline_execution_id: Optional[int] = None


@dataclass(slots=True)
class PromptContext:
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    package: dict[str, Any] | None = None
    package_version: Optional[str] = None
    generated_at: Optional[str] = None
    pipeline_execution_id: Optional[int] = None


@dataclass(slots=True)
class EmbeddingContext:
    status: dict[str, Any] = field(default_factory=dict)
    package_version: Optional[str] = None
    generated_at: Optional[str] = None
    pipeline_execution_id: Optional[int] = None


@dataclass(slots=True)
class IntelligenceContext:
    governance: Optional[GovernanceContext] = None
    semantics: Optional[SemanticContext] = None
    relationships: Optional[RelationshipContext] = None
    kpis: Optional[KPIContext] = None
    prompts: Optional[PromptContext] = None
    embeddings: Optional[EmbeddingContext] = None
    readiness: Optional[dict[str, Any]] = None
    pipeline_execution_id: Optional[int] = None


def context_to_dict(context: IntelligenceContext | None) -> dict[str, Any] | None:
    if context is None:
        return None
    payload = asdict(context)
    if payload.get("pipeline_execution_id") is None:
        payload.pop("pipeline_execution_id", None)
    return payload
