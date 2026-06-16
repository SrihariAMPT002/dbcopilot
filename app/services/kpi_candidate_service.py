"""KPI candidate generation with AI enrichment."""

from __future__ import annotations

import json
from typing import Any

from app.config.prompts import get_prompt_registry
from app.core.config import settings
from app.services.ai_observability_service import AIObservabilityService


class KPICandidateService:
    def __init__(self) -> None:
        self.registry = get_prompt_registry()

    async def generate_with_ai(
        self,
        *,
        database_context: dict[str, Any] | None = None,
        governance_package: list[dict[str, Any]] | None = None,
        semantic_package: dict[str, Any] | None = None,
        relationship_package: dict[str, Any] | None = None,
        graph_features: dict[str, Any] | None = None,
        candidates: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        deterministic = candidates or []
        rendered = self.registry.render_prompt(
            "kpi_candidate_discovery",
            {
                "database_context": database_context or {},
                "governance_package": governance_package or [],
                "semantic_package": semantic_package or {},
                "relationship_package": relationship_package or {},
                "graph_features": graph_features or {},
                "candidates": deterministic,
            },
            category="kpi",
        )
        observability = AIObservabilityService()
        try:
            result = await observability.generate(
                operation="chat",
                module="kpi_intelligence",
                artifact_type="kpi_candidate_discovery",
                prompt_id=rendered.metadata.id,
                prompt_version=rendered.metadata.version,
                model_name=settings.azure_openai_deployment,
                messages=[
                    {"role": "system", "content": rendered.system_message or "You are a KPI candidate inference engine."},
                    {"role": "user", "content": rendered.user_prompt},
                ],
                request_kwargs={"max_completion_tokens": 5000, "response_format": {"type": "json_object"}},
                completeness_score=0.0,
                coverage_score=0.0,
                confidence_score=0.0,
                execution_status="success",
                fallback_used=False,
                retry_count=0,
                extra_metadata={"feature": "kpi_candidates"},
            )
            payload = json.loads(result.content or "{}")
            enriched = payload.get("kpi_candidates")
            if isinstance(enriched, list) and enriched:
                return enriched
        except Exception:
            pass
        return deterministic

    NUMERIC_TOKENS = ("amount", "price", "total", "sum", "count", "qty", "quantity", "balance", "revenue", "cost", "amounts")
    DATE_TOKENS = ("date", "time", "created", "updated", "month", "day", "week", "hour", "year")
    WORKFLOW_TOKENS = ("status", "state", "stage", "event", "event_type", "event_name", "lifecycle", "workflow")

    def generate(
        self,
        *,
        database_semantics: dict[str, Any] | None = None,
        schema_semantics: list[dict[str, Any]] | None = None,
        relationship_intelligence: list[dict[str, Any]] | None = None,
        governance_intelligence: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()
        schema_semantics = schema_semantics or []
        governance_intelligence = governance_intelligence or []
        relationship_intelligence = relationship_intelligence or []

        for item in schema_semantics:
            table = str(item.get("table") or "").strip()
            semantic_summary = str(item.get("semantic_summary") or "").strip()
            if not table and not semantic_summary:
                continue
            score = self._score_text(f"{table} {semantic_summary}")
            if score <= 0:
                continue
            metric = self._derive_metric_name(table or semantic_summary, suffix="volume")
            self._add_candidate(candidates, seen, metric, "table_metric", score)

        for item in governance_intelligence:
            column = str(item.get("column") or item.get("column_name") or "").strip()
            if not column:
                continue
            score = self._score_column(column)
            if score <= 0:
                continue
            candidate_type = "trend_metric" if any(token in column.lower() for token in self.DATE_TOKENS) else "measure"
            metric = self._derive_metric_name(column, suffix="metric")
            self._add_candidate(candidates, seen, metric, candidate_type, score)

        for rel in relationship_intelligence:
            source = str(rel.get("source_table") or rel.get("source") or rel.get("source_table_name") or "").strip()
            target = str(rel.get("target_table") or rel.get("target") or rel.get("target_table_name") or "").strip()
            if not source and not target:
                continue
            relation_name = self._derive_metric_name(f"{source} to {target}".strip(), suffix="dependency")
            score = 0.5 + min(0.2, 0.05 * len(str(rel.get("join_columns") or rel.get("relationship_type") or "")))
            self._add_candidate(candidates, seen, relation_name, "relationship_metric", round(min(0.9, score), 2))

        domain = str((database_semantics or {}).get("business_domain") or "").strip()
        if domain:
            metric = self._derive_metric_name(domain, suffix="kpi")
            self._add_candidate(candidates, seen, metric, "domain_kpi", 0.45)

        return candidates

    def _score_text(self, text: str) -> float:
        lowered = text.lower()
        score = 0.0
        if any(token in lowered for token in self.NUMERIC_TOKENS):
            score += 0.45
        if any(token in lowered for token in self.DATE_TOKENS):
            score += 0.2
        if any(token in lowered for token in self.WORKFLOW_TOKENS):
            score += 0.15
        if any(token in lowered for token in ("rate", "ratio", "avg", "average", "conversion", "completion")):
            score += 0.25
        return round(min(0.9, score), 2)

    def _score_column(self, column: str) -> float:
        return self._score_text(column)

    @staticmethod
    def _derive_metric_name(value: str, *, suffix: str) -> str:
        cleaned = value.replace("_", " ").replace(".", " ").strip()
        if not cleaned:
            return f"{suffix}"
        words = [word for word in cleaned.split() if word]
        base = " ".join(word.capitalize() for word in words[:5])
        return f"{base} {suffix.capitalize()}".strip()

    @staticmethod
    def _add_candidate(
        candidates: list[dict[str, Any]],
        seen: set[str],
        metric: str,
        candidate_type: str,
        confidence: float,
    ) -> None:
        key = metric.lower()
        if not metric or key in seen:
            return
        seen.add(key)
        candidates.append(
            {
                "metric": metric,
                "candidate_type": candidate_type,
                "confidence": round(float(confidence), 2),
            }
        )
