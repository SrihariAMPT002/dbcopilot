"""Validation helpers for governance AI responses."""

from __future__ import annotations

import json
from typing import Any


class GovernanceValidatorService:
    REQUIRED_COLUMN_FIELDS = {
        "column_name",
        "is_pii",
        "pii_type",
        "risk_level",
        "confidence_score",
        "business_meaning",
        "governance_reasoning",
    }

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
        for key in ("table_summary", "business_purpose", "resolved_columns"):
            if key not in payload:
                raise ValueError(f"missing_required_fields:{key}")
        if not isinstance(payload.get("resolved_columns"), list):
            raise ValueError("missing_required_fields:resolved_columns")
        for item in payload["resolved_columns"]:
            if not isinstance(item, dict):
                raise ValueError("invalid_resolved_columns")
            missing = self.REQUIRED_COLUMN_FIELDS - set(item.keys())
            if missing:
                raise ValueError(f"missing_required_fields:{','.join(sorted(missing))}")
            confidence = float(item.get("confidence_score", 0.0) or 0.0)
            if confidence < 0.0 or confidence > 1.0:
                raise ValueError("invalid_confidence_score")
        return payload

