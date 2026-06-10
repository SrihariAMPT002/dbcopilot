"""
Relationship graph engine.

Builds a graph-aware view over discovered foreign-key relationships so the
system can reason about connectivity, join paths, depth, and cycles.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import networkx as nx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.metadata import (
    ConnectedDatabase,
    DatabaseColumn,
    DatabaseRelationship,
    DatabaseSchema,
    DatabaseTable,
    SchemaRelationshipGraph,
    SchemaSemantic,
    DatabaseSemantic,
)
from app.services.ai_observability_service import AIObservabilityService
from app.utils import safe_flush
from app.config.prompts import get_prompt_registry
from app.config.package_registry import package_is_enabled

logger = logging.getLogger(__name__)


@dataclass
class JoinColumnLink:
    source_column: str
    target_column: str


@dataclass
class GraphEdgeRecord:
    source_table_id: int
    target_table_id: int
    source_table_name: str
    target_table_name: str
    source_schema_name: str
    target_schema_name: str
    relationship_type: str
    join_columns: List[JoinColumnLink] = field(default_factory=list)
    relationship_strength: float = 1.0
    path_depth: int = 1
    is_circular: bool = False


@dataclass
class GraphNodeRecord:
    table_id: int
    schema_id: int
    schema_name: str
    table_name: str
    table_type: str
    degree: int
    in_degree: int
    out_degree: int
    depth: int
    is_isolated: bool


@dataclass
class GraphMetrics:
    table_count: int
    edge_count: int
    relationship_density: float
    graph_depth: int
    relationship_complexity: float = 0.0
    central_tables: List[str] = field(default_factory=list)
    isolated_tables: List[str] = field(default_factory=list)
    cycle_count: int = 0


@dataclass
class RelationshipGraphSnapshot:
    database_id: int
    database_name: str
    generated_at: datetime
    nodes: List[GraphNodeRecord] = field(default_factory=list)
    edges: List[GraphEdgeRecord] = field(default_factory=list)
    metrics: GraphMetrics | None = None
    cycles: List[List[str]] = field(default_factory=list)
    relationship_intelligence: dict[str, Any] = field(default_factory=dict)


@dataclass
class NeighborGraphSnapshot:
    table_id: int
    table_name: str
    schema_name: str
    neighbors: List[GraphNodeRecord] = field(default_factory=list)
    edges: List[GraphEdgeRecord] = field(default_factory=list)


@dataclass
class JoinStepRecord:
    source_table_id: int
    target_table_id: int
    source_table_name: str
    target_table_name: str
    relationship_type: str
    join_columns: List[JoinColumnLink] = field(default_factory=list)
    relationship_strength: float = 1.0


@dataclass
class JoinPathRecord:
    source_table_id: int
    target_table_id: int
    hops: int
    steps: List[JoinStepRecord] = field(default_factory=list)


@dataclass
class JoinPathsSnapshot:
    source_table_id: int
    target_table_id: int
    path_count: int
    paths: List[JoinPathRecord] = field(default_factory=list)
    message: str = "Join paths discovered."


@dataclass
class ExportBundle:
    format: str
    filename: str
    content: str


class RelationshipGraphEngine:
    """Builds and queries the schema relationship graph."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _fetch_database(self, database_id: int) -> ConnectedDatabase:
        result = await self.db.execute(
            select(ConnectedDatabase).where(ConnectedDatabase.id == database_id)
        )
        database = result.scalars().first()
        if not database:
            raise ValueError(f"Database {database_id} not found")
        return database

    async def _fetch_tables(self, database_id: int) -> List[DatabaseTable]:
        result = await self.db.execute(
            select(DatabaseTable)
            .join(DatabaseSchema)
            .options(
                selectinload(DatabaseTable.schema).selectinload(DatabaseSchema.connected_database),
                selectinload(DatabaseTable.columns),
                selectinload(DatabaseTable.relationships_from),
            )
            .where(DatabaseSchema.connected_db_id == database_id)
            .order_by(DatabaseSchema.name, DatabaseTable.name)
        )
        return result.scalars().unique().all()

    async def _fetch_table(self, table_id: int) -> DatabaseTable:
        result = await self.db.execute(
            select(DatabaseTable)
            .options(
                selectinload(DatabaseTable.schema).selectinload(DatabaseSchema.connected_database),
                selectinload(DatabaseTable.columns),
                selectinload(DatabaseTable.relationships_from),
            )
            .where(DatabaseTable.id == table_id)
        )
        table = result.scalars().first()
        if not table:
            raise ValueError(f"Table {table_id} not found")
        return table

    def _resolve_target_table_id(
        self,
        rel: DatabaseRelationship,
        table_index: Dict[Tuple[str, str], DatabaseTable],
        source_schema_name: str,
    ) -> Optional[int]:
        if rel.referenced_table_id:
            return rel.referenced_table_id
        schema_name = rel.referenced_schema or source_schema_name
        target = table_index.get((schema_name, rel.referenced_table_name))
        if target:
            return target.id
        for (schema, name), table in table_index.items():
            if name == rel.referenced_table_name and (rel.referenced_schema is None or rel.referenced_schema == schema):
                return table.id
        return None

    def _relationship_strength(self, source: DatabaseTable, target: DatabaseTable, rel: DatabaseRelationship) -> float:
        if source.id == target.id:
            return 0.75
        target_columns = {column.name: column for column in target.columns}
        referenced = target_columns.get(rel.referenced_column_name)
        if referenced and (referenced.is_primary_key or referenced.is_unique):
            return 1.0
        if referenced and referenced.is_indexed:
            return 0.92
        return 0.85

    def _shortest_depths(
        self,
        roots: List[int],
        adjacency: Dict[int, List[int]],
        tables: Dict[int, DatabaseTable],
    ) -> Dict[int, int]:
        depths = {table_id: 0 for table_id in tables}
        if roots:
            queue = deque([(root, 0) for root in roots])
            seen = set(roots)
            while queue:
                node, depth = queue.popleft()
                depths[node] = max(depths.get(node, 0), depth)
                for neighbor in adjacency.get(node, []):
                    if neighbor not in seen:
                        seen.add(neighbor)
                        queue.append((neighbor, depth + 1))
            return depths

        # Fallback for cyclic graphs: use an arbitrary BFS start per connected component.
        remaining = set(tables)
        while remaining:
            start = remaining.pop()
            queue = deque([(start, 0)])
            seen = {start}
            while queue:
                node, depth = queue.popleft()
                depths[node] = max(depths.get(node, 0), depth)
                for neighbor in adjacency.get(node, []):
                    if neighbor not in seen:
                        seen.add(neighbor)
                        remaining.discard(neighbor)
                        queue.append((neighbor, depth + 1))
        return depths

    def _graph_depth(self, adjacency: Dict[int, List[int]], tables: Dict[int, DatabaseTable]) -> int:
        if not tables:
            return 0
        max_depth = 0
        nodes = list(tables)
        undirected = self._undirected_adjacency(
            [
                GraphEdgeRecord(
                    source_table_id=src,
                    target_table_id=dst,
                    source_table_name="",
                    target_table_name="",
                    source_schema_name="",
                    target_schema_name="",
                    relationship_type="",
                )
                for src, dests in adjacency.items()
                for dst in dests
            ]
        )
        for start in nodes:
            queue = deque([(start, 0)])
            seen = {start}
            while queue:
                node, depth = queue.popleft()
                max_depth = max(max_depth, depth)
                for neighbor in undirected.get(node, []):
                    if neighbor not in seen:
                        seen.add(neighbor)
                        queue.append((neighbor, depth + 1))
        return max_depth

    def _build_nodes(
        self,
        tables: Dict[int, DatabaseTable],
        in_degree: Dict[int, int],
        out_degree: Dict[int, int],
        depths: Dict[int, int],
    ) -> List[GraphNodeRecord]:
        nodes: List[GraphNodeRecord] = []
        for table_id, table in tables.items():
            incoming = in_degree.get(table_id, 0)
            outgoing = out_degree.get(table_id, 0)
            degree = incoming + outgoing
            nodes.append(
                GraphNodeRecord(
                    table_id=table.id,
                    schema_id=table.schema_id,
                    schema_name=table.schema.name,
                    table_name=table.name,
                    table_type=table.table_type.value,
                    degree=degree,
                    in_degree=incoming,
                    out_degree=outgoing,
                    depth=depths.get(table_id, 0),
                    is_isolated=degree == 0,
                )
            )
        return sorted(nodes, key=lambda item: (item.schema_name, item.table_name))

    def _build_metrics(self, nodes: List[GraphNodeRecord], edges: List[GraphEdgeRecord], graph_depth: int, cycles: List[List[int]]) -> GraphMetrics:
        table_count = len(nodes)
        edge_count = len(edges)
        relationship_density = 0.0
        if table_count > 1:
            relationship_density = round(edge_count / (table_count * (table_count - 1) / 2), 4)

        ranked = sorted(nodes, key=lambda node: node.degree, reverse=True)
        central_tables = [f"{node.schema_name}.{node.table_name}" for node in ranked[:5] if node.degree > 0]
        isolated_tables = [f"{node.schema_name}.{node.table_name}" for node in nodes if node.is_isolated]
        relationship_complexity = round((edge_count + len(cycles) * 2 + graph_depth) / max(table_count, 1), 3)
        return GraphMetrics(
            table_count=table_count,
            edge_count=edge_count,
            relationship_density=relationship_density,
            graph_depth=graph_depth,
            relationship_complexity=relationship_complexity,
            central_tables=central_tables,
            isolated_tables=isolated_tables,
            cycle_count=len(cycles),
        )

    @staticmethod
    def _json_safe(value: Any) -> str:
        return json.dumps(value, default=str, indent=2)

    @staticmethod
    def _cluster_key(table_ids: list[int]) -> tuple[int, ...]:
        return tuple(sorted(table_ids))

    @staticmethod
    def _cluster_label(tables: dict[int, DatabaseTable], table_ids: list[int]) -> str:
        ordered = sorted(
            (tables[table_id] for table_id in table_ids if table_id in tables),
            key=lambda item: (item.schema.name, item.name),
        )
        if not ordered:
            return "empty-cluster"
        head = ordered[0]
        if len(ordered) == 1:
            return f"{head.schema.name}.{head.name}"
        return f"{head.schema.name}.{head.name} +{len(ordered) - 1}"

    @staticmethod
    def _limit_columns(table: DatabaseTable, max_columns: int = 8) -> list[dict[str, Any]]:
        return [
            {
                "name": column.name,
                "data_type": column.data_type,
                "is_primary_key": column.is_primary_key,
                "is_foreign_key": column.is_foreign_key,
                "is_unique": column.is_unique,
            }
            for column in sorted(table.columns, key=lambda item: item.ordinal_position or 0)[:max_columns]
        ]

    def _build_cluster_payload(
        self,
        database: ConnectedDatabase,
        tables: dict[int, DatabaseTable],
        edges: list[GraphEdgeRecord],
        cluster_table_ids: list[int],
        database_semantic: Optional[DatabaseSemantic],
        table_semantics: list[tuple[SchemaSemantic, DatabaseTable]],
    ) -> dict[str, Any]:
        cluster_tables = [tables[table_id] for table_id in cluster_table_ids if table_id in tables]
        cluster_table_ids_set = set(cluster_table_ids)
        cluster_edges = [
            edge for edge in edges
            if edge.source_table_id in cluster_table_ids_set and edge.target_table_id in cluster_table_ids_set
        ]
        semantic_lookup = {semantic.table_id: semantic for semantic, _ in table_semantics}
        return {
            "database_id": database.id,
            "database_name": database.display_name or database.name,
            "database_type": database.db_type.value,
            "cluster_id": self._cluster_key(cluster_table_ids),
            "cluster_label": self._cluster_label(tables, cluster_table_ids),
            "schema_summary": [
                {
                    "schema_name": table.schema.name,
                    "table_name": table.name,
                    "table_type": table.table_type.value,
                    "description": table.description,
                    "row_count": table.row_count,
                }
                for table in cluster_tables
            ],
            "relationships": [
                {
                    "source": f"{edge.source_schema_name}.{edge.source_table_name}",
                    "target": f"{edge.target_schema_name}.{edge.target_table_name}",
                    "relationship_type": edge.relationship_type,
                    "join_columns": [asdict(link) for link in edge.join_columns],
                    "strength": edge.relationship_strength,
                    "depth": edge.path_depth,
                }
                for edge in cluster_edges
            ],
            "columns": [
                {
                    "schema_name": table.schema.name,
                    "table_name": table.name,
                    "columns": self._limit_columns(table),
                }
                for table in cluster_tables
            ],
            "semantic": {
                "database_semantic": {
                    "business_domain": database_semantic.business_domain if database_semantic else None,
                    "business_summary": database_semantic.business_summary if database_semantic else None,
                    "analysis_notes": database_semantic.analysis_notes if database_semantic else None,
                    "key_entities": database_semantic.key_entities if database_semantic else [],
                },
                "table_semantics": [
                    {
                        "table_id": semantic.table_id,
                        "schema_name": table.schema.name,
                        "table_name": table.name,
                        "semantic_summary": semantic.semantic_summary,
                        "business_keywords": semantic.business_keywords,
                        "likely_usage": semantic.likely_usage,
                    }
                    for semantic, table in table_semantics
                    if semantic.table_id in cluster_table_ids_set
                ],
            },
            "relationship_graph": {
                "nodes": [
                    {
                        "table_id": table.id,
                        "schema_id": table.schema_id,
                        "schema_name": table.schema.name,
                        "table_name": table.name,
                        "table_type": table.table_type.value,
                    }
                    for table in cluster_tables
                ],
                "edges": [
                    {
                        "source_table_id": edge.source_table_id,
                        "target_table_id": edge.target_table_id,
                        "source_table_name": edge.source_table_name,
                        "target_table_name": edge.target_table_name,
                        "source_schema_name": edge.source_schema_name,
                        "target_schema_name": edge.target_schema_name,
                        "relationship_type": edge.relationship_type,
                    }
                    for edge in cluster_edges
                ],
            },
        }

    @staticmethod
    def _parse_json_object(text: str) -> dict[str, Any]:
        cleaned = (text or "").strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        if not cleaned:
            return {}
        try:
            parsed = json.loads(cleaned)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except Exception:
            return {"raw_response": cleaned}

    async def _fetch_semantics(
        self,
        database_id: int,
    ) -> tuple[Optional[DatabaseSemantic], list[tuple[SchemaSemantic, DatabaseTable]]]:
        database_semantic = await self.db.scalar(
            select(DatabaseSemantic).where(DatabaseSemantic.source_id == database_id)
        )
        result = await self.db.execute(
            select(SchemaSemantic, DatabaseTable)
            .join(DatabaseTable, SchemaSemantic.table_id == DatabaseTable.id)
            .join(DatabaseSchema, DatabaseTable.schema_id == DatabaseSchema.id)
            .where(DatabaseSchema.connected_db_id == database_id)
        )
        table_semantics = [
            (semantic, table)
            for semantic, table in result.all()
        ]
        return database_semantic, table_semantics

    def _cluster_tables(self, tables: list[DatabaseTable], edges: list[GraphEdgeRecord]) -> list[list[int]]:
        adjacency: dict[int, set[int]] = defaultdict(set)
        for table in tables:
            adjacency[table.id]
        for edge in edges:
            adjacency[edge.source_table_id].add(edge.target_table_id)
            adjacency[edge.target_table_id].add(edge.source_table_id)

        clusters: list[list[int]] = []
        seen: set[int] = set()
        for table in tables:
            if table.id in seen:
                continue
            queue = deque([table.id])
            seen.add(table.id)
            cluster: list[int] = []
            while queue:
                current = queue.popleft()
                cluster.append(current)
                for neighbor in adjacency.get(current, set()):
                    if neighbor not in seen:
                        seen.add(neighbor)
                        queue.append(neighbor)
            clusters.append(sorted(cluster))
        return sorted(clusters, key=lambda ids: (len(ids), ids))

    async def _analyze_cluster_relationships(
        self,
        database: ConnectedDatabase,
        tables: dict[int, DatabaseTable],
        edges: list[GraphEdgeRecord],
        cluster_table_ids: list[int],
        database_semantic: Optional[DatabaseSemantic],
        table_semantics: list[tuple[SchemaSemantic, DatabaseTable]],
    ) -> dict[str, Any]:
        if not package_is_enabled("relationship"):
            raise ValueError("Relationship package is disabled by registry")
        prompt_context = self._build_cluster_payload(
            database,
            tables,
            edges,
            cluster_table_ids,
            database_semantic,
            table_semantics,
        )
        registry = get_prompt_registry()
        discovery_prompt = registry.render_prompt("relationship_discovery", prompt_context, category="relationship")
        analysis_prompt = registry.render_prompt("business_relationship_analysis", prompt_context, category="relationship")
        observability = AIObservabilityService()
        result = await observability.generate(
            operation="chat",
            module="relationship_intelligence",
            artifact_type="relationship_analysis",
            prompt_id=discovery_prompt.metadata.id,
            prompt_version=discovery_prompt.metadata.version,
            database_id=database.id,
            database_name=database.display_name or database.name,
            model_name=settings.azure_openai_deployment or "azure_openai",
            messages=[
                {"role": "system", "content": analysis_prompt.system_message or discovery_prompt.system_message},
                {"role": "user", "content": "\n\n".join([discovery_prompt.user_prompt, analysis_prompt.user_prompt])},
            ],
            request_kwargs={"response_format": {"type": "json_object"}, "max_completion_tokens": 1200},
            completeness_score=1.0,
            coverage_score=min(1.0, len(cluster_table_ids) / max(1, len(tables))),
            confidence_score=0.0,
            extra_metadata={
                "feature": "relationship_analysis_cluster",
                "prompt_name": discovery_prompt.metadata.id,
                "artifact_type": "relationship_analysis",
                "cluster_size": len(cluster_table_ids),
                "cluster_label": prompt_context["cluster_label"],
            },
        )
        payload = self._parse_json_object(result.content or "")
        payload.setdefault("business_entity_graph", payload.get("business_entity_graph") or [])
        payload.setdefault("business_process_flows", payload.get("business_process_flows") or [])
        payload.setdefault("upstream_dependencies", payload.get("upstream_dependencies") or [])
        payload.setdefault("downstream_dependencies", payload.get("downstream_dependencies") or [])
        payload.setdefault("entity_lifecycle_descriptions", payload.get("entity_lifecycle_descriptions") or [])
        payload.setdefault("business_relationship_summary", payload.get("business_relationship_summary") or "")
        payload["confidence_score"] = float(payload.get("confidence_score", 0.7 if payload.get("business_relationship_summary") else 0.0) or 0.0)
        payload["prompt_name"] = discovery_prompt.metadata.id
        payload["prompt_version"] = str(discovery_prompt.metadata.version)
        payload["model_name"] = result.model_name
        payload["database_id"] = database.id
        payload["feature"] = "relationship_analysis_cluster"
        payload["trace_id"] = result.trace_id
        payload["trace_url"] = result.trace_url
        payload["source_prompt"] = discovery_prompt.user_prompt
        payload["analysis_prompt"] = analysis_prompt.user_prompt
        payload["cluster_id"] = self._cluster_key(cluster_table_ids)
        payload["cluster_label"] = prompt_context["cluster_label"]
        payload["cluster_table_ids"] = cluster_table_ids
        return payload

    async def _synthesize_relationship_intelligence(
        self,
        database: ConnectedDatabase,
        tables: list[DatabaseTable],
        edges: list[GraphEdgeRecord],
    ) -> dict[str, Any]:
        if not package_is_enabled("relationship"):
            raise ValueError("Relationship package is disabled by registry")
        database_semantic, table_semantics = await self._fetch_semantics(database.id)
        cluster_ids = self._cluster_tables(tables, edges)
        cluster_payloads = [
            await self._analyze_cluster_relationships(database, {table.id: table for table in tables}, edges, cluster_id, database_semantic, table_semantics)
            for cluster_id in cluster_ids
        ]

        summary_payload = {
            "database_id": database.id,
            "database_name": database.display_name or database.name,
            "database_type": database.db_type.value,
            "cluster_count": len(cluster_payloads),
            "clusters": [
                {
                    "cluster_id": payload.get("cluster_id"),
                    "cluster_label": payload.get("cluster_label"),
                    "cluster_size": len(payload.get("cluster_table_ids", [])),
                    "business_relationship_summary": payload.get("business_relationship_summary", ""),
                    "business_entity_graph": payload.get("business_entity_graph", []),
                    "business_process_flows": payload.get("business_process_flows", []),
                    "upstream_dependencies": payload.get("upstream_dependencies", []),
                    "downstream_dependencies": payload.get("downstream_dependencies", []),
                    "entity_lifecycle_descriptions": payload.get("entity_lifecycle_descriptions", []),
                    "confidence_score": payload.get("confidence_score", 0.0),
                }
                for payload in cluster_payloads
            ],
            "database_semantic": {
                "business_domain": database_semantic.business_domain if database_semantic else None,
                "business_summary": database_semantic.business_summary if database_semantic else None,
                "analysis_notes": database_semantic.analysis_notes if database_semantic else None,
                "key_entities": database_semantic.key_entities if database_semantic else [],
            },
            "semantic": {
                "database_semantic": {
                    "business_domain": database_semantic.business_domain if database_semantic else None,
                    "business_summary": database_semantic.business_summary if database_semantic else None,
                    "analysis_notes": database_semantic.analysis_notes if database_semantic else None,
                    "key_entities": database_semantic.key_entities if database_semantic else [],
                },
                "table_semantics": [],
            },
            "relationship_graph": {
                "nodes": [],
                "edges": [],
            },
            "relationships": [],
            "columns": [],
        }
        registry = get_prompt_registry()
        synthesis_prompt = registry.render_prompt("business_relationship_analysis", summary_payload, category="relationship")
        observability = AIObservabilityService()
        result = await observability.generate(
            operation="chat",
            module="relationship_intelligence",
            artifact_type="relationship_analysis",
            prompt_id=synthesis_prompt.metadata.id,
            prompt_version=synthesis_prompt.metadata.version,
            database_id=database.id,
            database_name=database.display_name or database.name,
            model_name=settings.azure_openai_deployment or "azure_openai",
            messages=[
                {"role": "system", "content": synthesis_prompt.system_message},
                {"role": "user", "content": synthesis_prompt.user_prompt},
            ],
            request_kwargs={"response_format": {"type": "json_object"}, "max_completion_tokens": 1200},
            completeness_score=1.0,
            coverage_score=min(1.0, len(cluster_payloads) / max(1, len(tables))),
            confidence_score=0.0,
            extra_metadata={
                "feature": "relationship_analysis_synthesis",
                "cluster_count": len(cluster_payloads),
                "table_count": len(tables),
                "relationship_count": len(edges),
            },
        )
        payload = self._parse_json_object(result.content or "")
        payload.setdefault("business_entity_graph", payload.get("business_entity_graph") or [])
        payload.setdefault("business_process_flows", payload.get("business_process_flows") or [])
        payload.setdefault("upstream_dependencies", payload.get("upstream_dependencies") or [])
        payload.setdefault("downstream_dependencies", payload.get("downstream_dependencies") or [])
        payload.setdefault("entity_lifecycle_descriptions", payload.get("entity_lifecycle_descriptions") or [])
        payload.setdefault("business_relationship_summary", payload.get("business_relationship_summary") or "")
        payload["cluster_summaries"] = summary_payload["clusters"]
        payload["cluster_count"] = len(cluster_payloads)
        payload["prompt_name"] = synthesis_prompt.metadata.id
        payload["prompt_version"] = str(synthesis_prompt.metadata.version)
        payload["model_name"] = result.model_name
        payload["database_id"] = database.id
        payload["feature"] = "relationship_analysis_synthesis"
        payload["trace_id"] = result.trace_id
        payload["trace_url"] = result.trace_url
        payload["source_prompt"] = synthesis_prompt.user_prompt
        payload["analysis_prompt"] = synthesis_prompt.user_prompt
        return payload

    async def build_relationship_graph(self, database_id: int, persist: bool = True) -> RelationshipGraphSnapshot:
        if not package_is_enabled("relationship"):
            raise ValueError("Relationship package is disabled by registry")
        database = await self._fetch_database(database_id)
        tables = await self._fetch_tables(database_id)
        if not tables:
            raise ValueError(f"Database {database_id} has no tables")

        table_index = {(table.schema.name, table.name): table for table in tables}
        table_by_id = {table.id: table for table in tables}

        edges: List[GraphEdgeRecord] = []
        for table in tables:
            for rel in table.relationships_from:
                target_id = self._resolve_target_table_id(rel, table_index, table.schema.name)
                if target_id is None or target_id not in table_by_id:
                    continue

                target = table_by_id[target_id]
                relationship_type = "self_fk" if table.id == target.id else "fk"
                join_columns = [JoinColumnLink(source_column=rel.column_name, target_column=rel.referenced_column_name)]
                edge = GraphEdgeRecord(
                    source_table_id=table.id,
                    target_table_id=target.id,
                    source_table_name=table.name,
                    target_table_name=target.name,
                    source_schema_name=table.schema.name,
                    target_schema_name=target.schema.name,
                    relationship_type=relationship_type,
                    join_columns=join_columns,
                    relationship_strength=self._relationship_strength(table, target, rel),
                    path_depth=1,
                    is_circular=table.id == target.id,
                )
                edges.append(edge)

        directed_graph = nx.DiGraph()
        undirected_graph = nx.Graph()
        for table in tables:
            directed_graph.add_node(table.id)
            undirected_graph.add_node(table.id)
        for edge in edges:
            directed_graph.add_edge(
                edge.source_table_id,
                edge.target_table_id,
                relationship_type=edge.relationship_type,
                join_columns=[asdict(link) for link in edge.join_columns],
                relationship_strength=edge.relationship_strength,
            )
            undirected_graph.add_edge(edge.source_table_id, edge.target_table_id)

        cycles = [
            cycle + [cycle[0]]
            for cycle in nx.simple_cycles(directed_graph)
            if cycle
        ]
        cycle_nodes = {node_id for cycle in cycles for node_id in cycle}
        for edge in edges:
            if edge.source_table_id in cycle_nodes and edge.target_table_id in cycle_nodes:
                edge.is_circular = True

        in_degree: Dict[int, int] = defaultdict(int)
        out_degree: Dict[int, int] = defaultdict(int)
        for edge in edges:
            out_degree[edge.source_table_id] += 1
            in_degree[edge.target_table_id] += 1

        roots = [table_id for table_id in table_by_id if in_degree.get(table_id, 0) == 0]
        depths = self._shortest_depths(roots, {node: list(directed_graph.successors(node)) for node in directed_graph.nodes}, table_by_id)
        for edge in edges:
            edge.path_depth = depths.get(edge.source_table_id, 0) + 1

        nodes = self._build_nodes(table_by_id, in_degree, out_degree, depths)
        graph_depth = 0
        if undirected_graph.number_of_nodes():
            for component in nx.connected_components(undirected_graph):
                subgraph = undirected_graph.subgraph(component)
                if subgraph.number_of_nodes() > 1:
                    lengths = dict(nx.all_pairs_shortest_path_length(subgraph))
                    graph_depth = max(
                        graph_depth,
                        max((max(path_lengths.values()) for path_lengths in lengths.values()), default=0),
                    )
        metrics = self._build_metrics(nodes, edges, graph_depth, cycles)
        relationship_intelligence = await self._synthesize_relationship_intelligence(database, tables, edges)
        snapshot = RelationshipGraphSnapshot(
            database_id=database.id,
            database_name=database.display_name or database.name,
            generated_at=datetime.now(timezone.utc),
            nodes=nodes,
            edges=edges,
            metrics=metrics,
            cycles=[
                [f"{table_by_id[node_id].schema.name}.{table_by_id[node_id].name}" for node_id in cycle if node_id in table_by_id]
                for cycle in cycles
            ],
            relationship_intelligence=relationship_intelligence,
        )

        if persist:
            await self._persist_graph(database_id, edges, relationship_intelligence)

        # Validate relationship prompts are loadable for downstream Prompt Studio / governance flows.
        try:
            registry = get_prompt_registry()
            prompt_context = {
                "database_name": database.display_name or database.name,
                "database_type": database.db_type.value,
                "schema_summary": [
                    {
                        "schema_name": table.schema.name,
                        "table_name": table.name,
                        "table_type": table.table_type.value,
                    }
                    for table in tables
                ],
                "relationships": [
                    {
                        "source": f"{edge.source_schema_name}.{edge.source_table_name}",
                        "target": f"{edge.target_schema_name}.{edge.target_table_name}",
                        "relationship_type": edge.relationship_type,
                    }
                    for edge in edges
                ],
                "columns": [
                    {
                        "schema_name": table.schema.name,
                        "table_name": table.name,
                        "columns": [column.name for column in table.columns],
                    }
                    for table in tables
                ],
                "relationship_graph": {
                    "nodes": [node.__dict__ for node in nodes],
                    "edges": [edge.__dict__ for edge in edges],
                },
                "semantic": {},
            }
            registry.render_prompt("relationship_discovery", prompt_context, category="relationship")
            registry.render_prompt("business_relationship_analysis", prompt_context, category="relationship")
        except Exception as exc:
            logger.debug("Relationship prompt validation skipped: %s", exc)

        return snapshot

    async def _persist_graph(self, database_id: int, edges: List[GraphEdgeRecord], intelligence: dict[str, Any]) -> None:
        await self.db.execute(
            delete(SchemaRelationshipGraph).where(SchemaRelationshipGraph.database_id == database_id)
        )
        for edge in edges:
            source = await self._fetch_table(edge.source_table_id)
            target = await self._fetch_table(edge.target_table_id)
            self.db.add(
                SchemaRelationshipGraph(
                    database_id=database_id,
                    source_table_id=edge.source_table_id,
                    target_table_id=edge.target_table_id,
                    source_table_name=source.name,
                    target_table_name=target.name,
                    source_schema_name=source.schema.name,
                    target_schema_name=target.schema.name,
                    relationship_type=edge.relationship_type,
                    join_columns=json.dumps([asdict(link) for link in edge.join_columns]),
                    relationship_strength=edge.relationship_strength,
                    path_depth=edge.path_depth,
                    is_circular=edge.is_circular,
                    business_entity_graph=self._json_safe(intelligence.get("business_entity_graph", [])),
                    business_process_flows=self._json_safe(intelligence.get("business_process_flows", [])),
                    upstream_dependencies=self._json_safe(intelligence.get("upstream_dependencies", [])),
                    downstream_dependencies=self._json_safe(intelligence.get("downstream_dependencies", [])),
                    entity_lifecycle_descriptions=self._json_safe(intelligence.get("entity_lifecycle_descriptions", [])),
                    ai_summary=intelligence.get("business_relationship_summary"),
                    ai_confidence=float(intelligence.get("confidence_score", 0.0) or 0.0),
                    ai_model_name=intelligence.get("model_name"),
                    ai_prompt_id=intelligence.get("prompt_name"),
                    ai_prompt_version=str(intelligence.get("prompt_version", "")) or None,
                )
            )
        await safe_flush(self.db)

    def _edge_lookup(self, edges: List[GraphEdgeRecord]) -> Dict[Tuple[int, int], GraphEdgeRecord]:
        lookup: Dict[Tuple[int, int], GraphEdgeRecord] = {}
        for edge in edges:
            lookup[(edge.source_table_id, edge.target_table_id)] = edge
            lookup[(edge.target_table_id, edge.source_table_id)] = edge
        return lookup

    def _normalize_step(
        self,
        edge: GraphEdgeRecord,
        from_table: int,
        to_table: int,
    ) -> JoinStepRecord:
        if edge.source_table_id == from_table and edge.target_table_id == to_table:
            return JoinStepRecord(
                source_table_id=from_table,
                target_table_id=to_table,
                source_table_name=edge.source_table_name,
                target_table_name=edge.target_table_name,
                relationship_type=edge.relationship_type,
                join_columns=edge.join_columns,
                relationship_strength=edge.relationship_strength,
            )

        swapped_columns = [
            JoinColumnLink(source_column=link.target_column, target_column=link.source_column)
            for link in edge.join_columns
        ]
        return JoinStepRecord(
            source_table_id=from_table,
            target_table_id=to_table,
            source_table_name=edge.target_table_name,
            target_table_name=edge.source_table_name,
            relationship_type=f"{edge.relationship_type}_reversed",
            join_columns=swapped_columns,
            relationship_strength=edge.relationship_strength,
        )

    async def get_relationship_graph(self, database_id: int) -> RelationshipGraphSnapshot:
        return await self.build_relationship_graph(database_id, persist=True)

    async def get_neighbors(self, table_id: int, depth: int = 1) -> NeighborGraphSnapshot:
        table = await self._fetch_table(table_id)
        graph = await self.build_relationship_graph(table.schema.connected_db_id, persist=False)
        lookup = {node.table_id: node for node in graph.nodes}
        adjacency: Dict[int, List[GraphEdgeRecord]] = defaultdict(list)
        for edge in graph.edges:
            adjacency[edge.source_table_id].append(edge)
            adjacency[edge.target_table_id].append(edge)

        seen = {table_id}
        queue = deque([(table_id, 0)])
        neighbors: Dict[int, GraphNodeRecord] = {}
        edges: List[GraphEdgeRecord] = []
        while queue:
            node_id, dist = queue.popleft()
            if dist >= depth:
                continue
            for edge in adjacency.get(node_id, []):
                neighbor_id = edge.target_table_id if edge.source_table_id == node_id else edge.source_table_id
                edges.append(edge)
                if neighbor_id not in seen:
                    seen.add(neighbor_id)
                    if neighbor_id in lookup:
                        neighbors[neighbor_id] = lookup[neighbor_id]
                    queue.append((neighbor_id, dist + 1))

        return NeighborGraphSnapshot(
            table_id=table.id,
            table_name=table.name,
            schema_name=table.schema.name,
            neighbors=sorted(neighbors.values(), key=lambda item: (item.schema_name, item.table_name)),
            edges=edges,
        )

    async def get_join_paths(
        self,
        source_table_id: int,
        target_table_id: int,
        max_paths: int = 5,
    ) -> JoinPathsSnapshot:
        source = await self._fetch_table(source_table_id)
        target = await self._fetch_table(target_table_id)
        graph = await self.build_relationship_graph(source.schema.connected_db_id, persist=False)
        edge_lookup = self._edge_lookup(graph.edges)
        adjacency: Dict[int, List[Tuple[int, GraphEdgeRecord]]] = defaultdict(list)
        for edge in graph.edges:
            adjacency[edge.source_table_id].append((edge.target_table_id, edge))
            adjacency[edge.target_table_id].append((edge.source_table_id, edge))

        queue = deque([source_table_id])
        distances = {source_table_id: 0}
        parents: Dict[int, List[Tuple[int, GraphEdgeRecord]]] = defaultdict(list)
        while queue:
            node = queue.popleft()
            for neighbor, edge in adjacency.get(node, []):
                if neighbor not in distances:
                    distances[neighbor] = distances[node] + 1
                    parents[neighbor].append((node, edge))
                    queue.append(neighbor)
                elif distances[neighbor] == distances[node] + 1:
                    parents[neighbor].append((node, edge))

        if target_table_id not in distances:
            return JoinPathsSnapshot(
                source_table_id=source_table_id,
                target_table_id=target_table_id,
                path_count=0,
                paths=[],
                message="No join path found.",
            )

        paths: List[JoinPathRecord] = []

        def backtrack(node: int, steps: List[JoinStepRecord]) -> None:
            if len(paths) >= max_paths:
                return
            if node == source_table_id:
                paths.append(
                    JoinPathRecord(
                        source_table_id=source_table_id,
                        target_table_id=target_table_id,
                        hops=len(steps),
                        steps=list(reversed(steps)),
                    )
                )
                return

            for prev, edge in parents.get(node, []):
                step = self._normalize_step(edge, prev, node)
                backtrack(prev, steps + [step])

        backtrack(target_table_id, [])

        return JoinPathsSnapshot(
            source_table_id=source_table_id,
            target_table_id=target_table_id,
            path_count=len(paths),
            paths=paths,
            message="Join path(s) discovered.",
        )

    def export_graph(self, snapshot: RelationshipGraphSnapshot, export_format: str = "json") -> ExportBundle:
        export_format = export_format.lower()
        if export_format == "json":
            payload = json.dumps(asdict(snapshot), default=str, indent=2)
            return ExportBundle(
                format="json",
                filename=f"relationship-graph-{snapshot.database_id}.json",
                content=payload,
            )

        if export_format == "markdown":
            lines = [
                f"# Relationship Graph: {snapshot.database_name}",
                "",
                f"- Tables: {snapshot.metrics.table_count if snapshot.metrics else 0}",
                f"- Edges: {snapshot.metrics.edge_count if snapshot.metrics else 0}",
                f"- Density: {snapshot.metrics.relationship_density if snapshot.metrics else 0}",
                f"- Depth: {snapshot.metrics.graph_depth if snapshot.metrics else 0}",
                "",
                "## Central Tables",
            ]
            for item in (snapshot.metrics.central_tables if snapshot.metrics else []):
                lines.append(f"- {item}")
            lines.extend(["", "## Isolated Tables"])
            for item in (snapshot.metrics.isolated_tables if snapshot.metrics else []):
                lines.append(f"- {item}")
            lines.extend(["", "## Relationships"])
            for edge in snapshot.edges:
                join_text = ", ".join(
                    f"{item.source_column}={item.target_column}" for item in edge.join_columns
                )
                lines.append(
                    f"- {edge.source_schema_name}.{edge.source_table_name} -> "
                    f"{edge.target_schema_name}.{edge.target_table_name} "
                    f"({edge.relationship_type}; {join_text}; strength={edge.relationship_strength})"
                )
            if snapshot.cycles:
                lines.extend(["", "## Cycles"])
                for cycle in snapshot.cycles:
                    lines.append(f"- {' -> '.join(cycle)}")
            return ExportBundle(
                format="markdown",
                filename=f"relationship-graph-{snapshot.database_id}.md",
                content="\n".join(lines),
            )

        if export_format == "diagram":
            lines = ["graph TD"]
            for node in snapshot.nodes:
                label = f"{node.schema_name}.{node.table_name}".replace("\"", "\\\"")
                lines.append(f'  T{node.table_id}["{label}"]')
            for edge in snapshot.edges:
                label = ", ".join(
                    f"{item.source_column}->{item.target_column}" for item in edge.join_columns
                )
                lines.append(
                    f"  T{edge.source_table_id} -->|{label}| T{edge.target_table_id}"
                )
            return ExportBundle(
                format="diagram",
                filename=f"relationship-graph-{snapshot.database_id}.mmd",
                content="\n".join(lines),
            )

        raise ValueError(f"Unsupported export format: {export_format}")
