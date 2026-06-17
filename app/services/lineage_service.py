"""Lineage extraction for relationships."""

from __future__ import annotations

from typing import Any


class LineageService:
    def build_lineage(self, *, relationship_packages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        lineage: list[dict[str, Any]] = []
        for package in relationship_packages:
            cluster_id = self._safe_get(package, "cluster_id")
            entity_graph = self._safe_get(package, "entity_graph", []) or []
            lifecycle_flows = self._safe_get(package, "lifecycle_flows", []) or []
            for edge in self._iter_items(entity_graph):
                normalized = self._normalize_edge(edge, default_type="fk")
                normalized["cluster_id"] = cluster_id
                lineage.append(normalized)
            for flow in self._iter_items(lifecycle_flows):
                normalized = self._normalize_edge(flow, default_type="lifecycle")
                normalized["cluster_id"] = cluster_id
                lineage.append(normalized)
        return lineage

    @staticmethod
    def _safe_get(value: Any, key: str, default: Any = None) -> Any:
        if isinstance(value, dict):
            return value.get(key, default)
        return getattr(value, key, default)

    @staticmethod
    def _iter_items(value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return [value]

    def _normalize_edge(self, edge: Any, *, default_type: str) -> dict[str, Any]:
        if isinstance(edge, dict):
            source = edge.get("source") or edge.get("from") or edge.get("left") or edge.get("origin")
            target = edge.get("target") or edge.get("to") or edge.get("right") or edge.get("destination")
            relationship_type = edge.get("relationship_type") or edge.get("type") or default_type
            return {
                "source": source,
                "target": target,
                "relationship_type": relationship_type,
                "evidence": edge,
            }

        if isinstance(edge, str):
            return {
                "source": edge,
                "target": None,
                "relationship_type": default_type,
                "evidence": {"summary": edge},
            }

        return {
            "source": self._safe_get(edge, "source") or self._safe_get(edge, "from"),
            "target": self._safe_get(edge, "target") or self._safe_get(edge, "to"),
            "relationship_type": self._safe_get(edge, "relationship_type", default_type),
            "evidence": edge,
        }
