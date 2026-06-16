"""Graph feature extraction for relationship intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import networkx as nx


@dataclass
class GraphFeatureBundle:
    graph_metrics: dict[str, Any]
    centrality: dict[str, float]
    hub_analysis: list[dict[str, Any]]
    communities: list[dict[str, Any]]
    evidence: list[dict[str, Any]]


class GraphFeatureService:
    def build(self, *, tables: list[dict[str, Any]], relationships: list[dict[str, Any]]) -> GraphFeatureBundle:
        graph = nx.DiGraph()
        for table in tables:
            graph.add_node(table["table_id"], **table)
        for rel in relationships:
            graph.add_edge(rel["source_table_id"], rel["target_table_id"], **rel)

        undirected = graph.to_undirected()
        degree = dict(graph.degree())
        betweenness = nx.betweenness_centrality(undirected) if undirected.number_of_nodes() > 1 else {}
        closeness = nx.closeness_centrality(undirected) if undirected.number_of_nodes() > 1 else {}
        pagerank = nx.pagerank(undirected) if undirected.number_of_nodes() > 1 else {}
        communities = self._communities(undirected)
        hubs = self._hub_analysis(degree, pagerank, tables)
        density = nx.density(undirected) if undirected.number_of_nodes() > 1 else 0.0
        graph_metrics = {
            "node_count": graph.number_of_nodes(),
            "edge_count": graph.number_of_edges(),
            "density": round(float(density), 4),
            "connected_components": nx.number_connected_components(undirected) if undirected.number_of_nodes() else 0,
            "strongly_connected_components": nx.number_weakly_connected_components(graph) if graph.number_of_nodes() else 0,
            "centrality": {
                "betweenness": betweenness,
                "closeness": closeness,
                "pagerank": pagerank,
            },
            "community_count": len(communities),
        }
        evidence = [
            {"source": "graph", "metrics": graph_metrics},
            {"source": "centrality", "values": {"betweenness": betweenness, "closeness": closeness, "pagerank": pagerank}},
            {"source": "hubs", "values": hubs},
            {"source": "communities", "values": communities},
        ]
        return GraphFeatureBundle(
            graph_metrics=graph_metrics,
            centrality=pagerank,
            hub_analysis=hubs,
            communities=communities,
            evidence=evidence,
        )

    def _communities(self, graph: nx.Graph) -> list[dict[str, Any]]:
        if graph.number_of_nodes() == 0:
            return []
        try:
            from networkx.algorithms.community import greedy_modularity_communities

            communities = list(greedy_modularity_communities(graph)) if graph.number_of_edges() else [{node} for node in graph.nodes()]
        except Exception:
            communities = [{node} for node in graph.nodes()]
        return [
            {"community_id": idx + 1, "nodes": sorted(list(community)), "size": len(community)}
            for idx, community in enumerate(communities)
        ]

    def _hub_analysis(self, degree: dict[int, int], pagerank: dict[int, float], tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ranked = sorted(tables, key=lambda t: (degree.get(t["table_id"], 0), pagerank.get(t["table_id"], 0.0)), reverse=True)
        return [
            {
                "table_id": table["table_id"],
                "table_name": table["table_name"],
                "schema_name": table["schema_name"],
                "degree": degree.get(table["table_id"], 0),
                "pagerank": round(float(pagerank.get(table["table_id"], 0.0)), 6),
                "role": "hub" if idx < 5 and degree.get(table["table_id"], 0) > 0 else "node",
            }
            for idx, table in enumerate(ranked[:10])
        ]

