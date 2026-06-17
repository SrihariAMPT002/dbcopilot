"""Validation helpers for relationship AI responses."""

from __future__ import annotations

import json
from typing import Any


class RelationshipValidatorService:
    REQUIRED_FIELDS = {"cluster_summary", "confidence_score", "entity_graph", "lifecycle_flows"}

    @staticmethod
    def _normalize_flow(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            source = value.get("source") or value.get("from") or value.get("stage") or value.get("name")
            target = value.get("target") or value.get("to")
            summary = value.get("summary") or value.get("description") or value.get("text") or value.get("note")
            return {
                "source": source,
                "target": target,
                "summary": summary or (str(value) if value else ""),
                "description": value.get("description") or summary or "",
            }
        text = str(value).strip()
        if not text:
            return {"summary": ""}
        if "->" in text:
            left, right = [part.strip() for part in text.split("->", 1)]
            return {"source": left or None, "target": right or None, "summary": text, "description": text}
        if ":" in text:
            left, right = [part.strip() for part in text.split(":", 1)]
            return {"stage": left or None, "description": right or None, "summary": text}
        return {"summary": text, "description": text}

    @classmethod
    def _normalize_list(cls, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                normalized.append(item)
            elif isinstance(item, str) and item.strip():
                normalized.append(cls._normalize_flow(item))
        return normalized

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
        payload["entity_graph"] = self._normalize_list(payload.get("entity_graph"))
        payload["lifecycle_flows"] = self._normalize_list(payload.get("lifecycle_flows"))
        payload["hidden_relationships"] = self._normalize_list(payload.get("hidden_relationships", []))
        payload["upstream_dependencies"] = self._normalize_list(payload.get("upstream_dependencies", []))
        payload["downstream_dependencies"] = self._normalize_list(payload.get("downstream_dependencies", []))
        payload["evidence"] = self._normalize_list(payload.get("evidence", []))
        payload.setdefault("cluster_confidence", payload.get("confidence_score", 0.0))
        return payload
