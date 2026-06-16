"""Scoring for relationship clusters."""

from __future__ import annotations

from typing import Any


class ClusterScoringService:
    def score(self, *, graph_metrics: dict[str, Any], cluster_size: int, relationship_count: int, ai_confidence: float) -> dict[str, Any]:
        density = float(graph_metrics.get("density", 0.0) or 0.0)
        centrality = graph_metrics.get("centrality", {}).get("pagerank", {}) if isinstance(graph_metrics.get("centrality"), dict) else {}
        top_centrality = max(centrality.values(), default=0.0) if isinstance(centrality, dict) else 0.0
        hub_bonus = min(0.2, top_centrality * 0.2)
        structural = min(1.0, 0.25 + density + min(0.25, relationship_count / max(1, cluster_size * 4)))
        confidence = max(0.0, min(1.0, (structural * 0.55) + (ai_confidence * 0.35) + hub_bonus))
        return {
            "centrality_score": round(top_centrality, 6),
            "hub_score": round(hub_bonus, 6),
            "community_score": round(min(1.0, density + 0.2), 6),
            "confidence_score": round(confidence, 6),
        }

