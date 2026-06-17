"""Canonical mapping helpers for relationship intelligence packages."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from app.models.metadata import RelationshipPackage


@dataclass(slots=True)
class RelationshipPackageDTO:
    id: int
    database_id: int
    cluster_id: str
    domain_name: Optional[str]
    cluster_summary: Optional[str]
    source_table_name: Optional[str]
    target_table_name: Optional[str]
    entity_graph: list[dict[str, Any]]
    lifecycle_flows: list[dict[str, Any]]
    confidence_score: float
    prompt_id: Optional[str]
    prompt_version: Optional[str]
    model_name: Optional[str]
    trace_id: Optional[str]


def _coerce_scalar(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_item(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        item = dict(value)
        summary = _coerce_scalar(item.get("summary") or item.get("description") or item.get("note") or item.get("text"))
        if summary and not item.get("summary"):
            item["summary"] = summary
        if summary and not item.get("description"):
            item["description"] = summary
        if item.get("stage") is None and item.get("name"):
            item["stage"] = _coerce_scalar(item.get("name"))
        if item.get("source") is None and item.get("from"):
            item["source"] = _coerce_scalar(item.get("from"))
        if item.get("target") is None and item.get("to"):
            item["target"] = _coerce_scalar(item.get("to"))
        return item
    text = _coerce_scalar(value)
    if not text:
        return {}
    if "->" in text:
        left, right = [part.strip() for part in text.split("->", 1)]
        return {
            "source": left or None,
            "target": right or None,
            "summary": text,
            "description": right or text,
        }
    if ":" in text:
        left, right = [part.strip() for part in text.split(":", 1)]
        return {
            "stage": left or None,
            "description": right or None,
            "summary": text,
        }
    return {"summary": text, "description": text}


def _as_dict_list(value: Any) -> list[dict[str, Any]]:
    if not value:
        return []
    if isinstance(value, list):
        return [_normalize_item(item) for item in value if _normalize_item(item)]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return [_normalize_item(value)]
        if isinstance(parsed, list):
            return [_normalize_item(item) for item in parsed if _normalize_item(item)]
    normalized = _normalize_item(value)
    return [normalized] if normalized else []


def normalize_lifecycle_flows(flows: Any) -> list[dict[str, Any]]:
    return _as_dict_list(flows)


def normalize_relationship_items(items: Any) -> list[dict[str, Any]]:
    return _as_dict_list(items)


def _table_name(value: Any) -> Optional[str]:
    if value is None:
        return None
    for key in ("name", "table_name"):
        resolved = getattr(value, key, None)
        if resolved:
            return str(resolved)
    if isinstance(value, dict):
        for key in ("name", "table_name"):
            resolved = value.get(key)
            if resolved:
                return str(resolved)
    if isinstance(value, str):
        return value
    return None


def relationship_package_to_dto(package: RelationshipPackage | Any) -> RelationshipPackageDTO:
    source_table_name = _table_name(getattr(package, "source_table", None))
    target_table_name = _table_name(getattr(package, "target_table", None))
    if source_table_name is None:
        source_table_name = _table_name(getattr(package, "source_table_name", None))
    if target_table_name is None:
        target_table_name = _table_name(getattr(package, "target_table_name", None))
    return RelationshipPackageDTO(
        id=int(getattr(package, "id", 0) or 0),
        database_id=int(getattr(package, "database_id", 0) or 0),
        cluster_id=str(getattr(package, "cluster_id", "") or ""),
        domain_name=getattr(package, "domain_name", None),
        cluster_summary=getattr(package, "cluster_summary", None),
        source_table_name=source_table_name,
        target_table_name=target_table_name,
        entity_graph=normalize_relationship_items(getattr(package, "entity_graph", None)),
        lifecycle_flows=normalize_lifecycle_flows(getattr(package, "lifecycle_flows", None)),
        confidence_score=float(getattr(package, "confidence_score", 0.0) or 0.0),
        prompt_id=getattr(package, "prompt_id", None),
        prompt_version=getattr(package, "prompt_version", None),
        model_name=getattr(package, "model_name", None),
        trace_id=getattr(package, "trace_id", None),
    )
