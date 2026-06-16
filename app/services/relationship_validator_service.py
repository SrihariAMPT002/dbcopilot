"""Validation helpers for relationship AI responses."""

from __future__ import annotations

import json
from typing import Any


class RelationshipValidatorService:
    REQUIRED_FIELDS = {"cluster_summary", "confidence_score", "entity_graph", "lifecycle_flows"}

    def parse_and_validate(self, content: str) -> dict[str, Any]:
        cleaned = (content or "").strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        if not cleaned:
            raise ValueError("empty_ai_response")
        try:
            payload = json.loads(cleaned)
        except Exception as exc:
            raise ValueError("invalid_json") from exc
        if not isinstance(payload, dict):
            raise ValueError("invalid_json")
        missing = [field for field in self.REQUIRED_FIELDS if field not in payload]
        if missing:
            raise ValueError(f"missing_required_fields:{','.join(missing)}")
        if not isinstance(payload.get("entity_graph"), list):
            raise ValueError("missing_required_fields:entity_graph")
        if not isinstance(payload.get("lifecycle_flows"), list):
            raise ValueError("missing_required_fields:lifecycle_flows")
        payload.setdefault("cluster_confidence", payload.get("confidence_score", 0.0))
        payload.setdefault("hidden_relationships", [])
        payload.setdefault("upstream_dependencies", [])
        payload.setdefault("downstream_dependencies", [])
        payload.setdefault("evidence", [])
        return payload
