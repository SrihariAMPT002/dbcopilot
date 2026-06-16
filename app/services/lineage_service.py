"""Lineage extraction for relationships."""

from __future__ import annotations

from typing import Any


class LineageService:
    def build_lineage(self, *, relationship_packages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        lineage: list[dict[str, Any]] = []
        for package in relationship_packages:
            cluster_id = package.get("cluster_id")
            for edge in package.get("entity_graph", []):
                lineage.append(
                    {
                        "cluster_id": cluster_id,
                        "source": edge.get("source") or edge.get("from"),
                        "target": edge.get("target") or edge.get("to"),
                        "relationship_type": edge.get("relationship_type") or "fk",
                        "evidence": edge,
                    }
                )
            for flow in package.get("lifecycle_flows", []):
                lineage.append(
                    {
                        "cluster_id": cluster_id,
                        "source": flow.get("source") or flow.get("from"),
                        "target": flow.get("target") or flow.get("to"),
                        "relationship_type": flow.get("relationship_type") or "lifecycle",
                        "evidence": flow,
                    }
                )
        return lineage

