"""Graph-aware retrieval on top of relationship intelligence."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.schema_engine.relationship_graph import RelationshipGraphEngine


@dataclass
class GraphRetrievalResult:
    database_id: Optional[int]
    query: str
    latency_ms: float
    neighbors: list[dict[str, Any]] = field(default_factory=list)
    shortest_paths: list[dict[str, Any]] = field(default_factory=list)
    contextual_retrieval: list[dict[str, Any]] = field(default_factory=list)
    lineage: list[dict[str, Any]] = field(default_factory=list)


class GraphRetrievalService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.engine = RelationshipGraphEngine(db)

    @staticmethod
    def _table_name_from_query(query: str) -> str:
        tokens = [token for token in query.replace(".", " ").split() if token]
        return tokens[-1].lower() if tokens else ""

    async def retrieve(
        self,
        query: str,
        *,
        database_id: Optional[int] = None,
        table_id: Optional[int] = None,
        related_table_id: Optional[int] = None,
        depth: int = 2,
        max_paths: int = 5,
    ) -> GraphRetrievalResult:
        start = time.perf_counter()
        if database_id is None and table_id is not None:
            table = await self.engine._fetch_table(table_id)
            database_id = table.schema.connected_db_id
        if database_id is None:
            raise ValueError("database_id or table_id is required")

        graph = await self.engine.get_relationship_graph(database_id)
        nodes = {node.table_id: node for node in graph.nodes}
        edges = graph.edges
        lineage = []
        for package in graph.relationship_intelligence.get("packages", []) if isinstance(graph.relationship_intelligence, dict) else []:
            lineage.extend(package.get("entity_graph") or [])
            lineage.extend(package.get("lifecycle_flows") or [])

        neighbors: list[dict[str, Any]] = []
        if table_id is not None and table_id in nodes:
            snapshot = await self.engine.get_neighbors(table_id, depth=depth)
            neighbors = [self._node_to_dict(item) for item in snapshot.neighbors]

        shortest_paths: list[dict[str, Any]] = []
        if table_id is not None and related_table_id is not None:
            paths = await self.engine.get_join_paths(table_id, related_table_id, max_paths=max_paths)
            shortest_paths = [self._path_to_dict(path) for path in paths.paths]

        contextual_retrieval: list[dict[str, Any]] = []
        query_table = self._table_name_from_query(query)
        for node in graph.nodes:
            if query_table and query_table in f"{node.schema_name}.{node.table_name}".lower():
                contextual_retrieval.append(self._node_to_dict(node))
        contextual_retrieval.extend(neighbors)
        contextual_retrieval = self._dedupe(contextual_retrieval)

        return GraphRetrievalResult(
            database_id=database_id,
            query=query,
            latency_ms=(time.perf_counter() - start) * 1000,
            neighbors=neighbors,
            shortest_paths=shortest_paths,
            contextual_retrieval=contextual_retrieval,
            lineage=lineage,
        )

    @staticmethod
    def _node_to_dict(node: Any) -> dict[str, Any]:
        return {
            "table_id": node.table_id,
            "schema_id": node.schema_id,
            "schema_name": node.schema_name,
            "table_name": node.table_name,
            "table_type": node.table_type,
            "degree": node.degree,
            "in_degree": node.in_degree,
            "out_degree": node.out_degree,
            "depth": node.depth,
            "is_isolated": node.is_isolated,
        }

    @staticmethod
    def _path_to_dict(path: Any) -> dict[str, Any]:
        return {
            "source_table_id": path.source_table_id,
            "target_table_id": path.target_table_id,
            "hops": path.hops,
            "steps": [
                {
                    "source_table_id": step.source_table_id,
                    "target_table_id": step.target_table_id,
                    "source_table_name": step.source_table_name,
                    "target_table_name": step.target_table_name,
                    "relationship_type": step.relationship_type,
                    "join_columns": [
                        {"source_column": col.source_column, "target_column": col.target_column}
                        for col in step.join_columns
                    ],
                    "relationship_strength": step.relationship_strength,
                }
                for step in path.steps
            ],
        }

    @staticmethod
    def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[Any, ...]] = set()
        unique: list[dict[str, Any]] = []
        for item in items:
            key = (item.get("table_id"), item.get("schema_name"), item.get("table_name"))
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

