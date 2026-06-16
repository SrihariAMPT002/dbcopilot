"""Validation helpers for semantic AI responses."""

from __future__ import annotations

import json
from typing import Any


class SemanticValidatorService:
    REQUIRED_FIELDS = {"business_domain", "semantic_summary", "business_entities", "business_processes", "business_capabilities", "table_semantics"}

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
        if not isinstance(payload.get("table_semantics"), list):
            raise ValueError("missing_required_fields:table_semantics")
        return payload

