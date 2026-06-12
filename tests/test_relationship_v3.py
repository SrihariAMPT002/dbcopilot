from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.schema_engine.relationship_graph import GraphEdgeRecord, JoinColumnLink, RelationshipGraphEngine


def _table(table_id: int, name: str, schema_name: str = "public"):
    return SimpleNamespace(
        id=table_id,
        schema_id=1,
        schema=SimpleNamespace(name=schema_name),
        name=name,
        description=f"{name} table",
        table_type=SimpleNamespace(value="table"),
        row_count=10,
        columns=[
            SimpleNamespace(id=table_id * 10, name="id", is_primary_key=True, is_foreign_key=False, ordinal_position=1),
            SimpleNamespace(id=table_id * 10 + 1, name="email", is_primary_key=False, is_foreign_key=False, ordinal_position=2),
        ],
    )


def test_build_cluster_package_excludes_schema_and_column_dumps():
    engine = RelationshipGraphEngine(AsyncMock())
    customers = _table(1, "customers")
    orders = _table(2, "orders")
    tables = {1: customers, 2: orders}
    edges = [
        GraphEdgeRecord(
            source_table_id=1,
            target_table_id=2,
            source_table_name="customers",
            target_table_name="orders",
            source_schema_name="public",
            target_schema_name="public",
            relationship_type="fk",
            join_columns=[JoinColumnLink(source_column="id", target_column="customer_id")],
        )
    ]
    pii_map = {
        12: SimpleNamespace(is_pii=True, risk_level="high"),
    }
    package = engine._build_cluster_package(
        SimpleNamespace(id=1, display_name="Demo", name="demo", db_type=SimpleNamespace(value="postgresql")),
        tables,
        edges,
        [1, 2],
        {
            "database_id": 1,
            "table_count": 2,
            "packages": [
                {
                    "schema_name": "public",
                    "table_name": "customers",
                    "pii_columns": [{"column_name": "email", "pii_type": "email"}],
                    "risk_columns": [],
                }
            ],
        },
        {
            "business_domain": "CRM",
            "semantic_summary": "Customer data",
            "business_capabilities": ["Sales"],
            "business_entities": ["customers"],
            "business_processes": ["Onboarding"],
            "table_semantics": [
                {
                    "schema_name": "public",
                    "table_name": "customers",
                    "semantic_summary": "Customer master",
                    "business_capabilities": ["Sales"],
                    "business_entities": ["customer"],
                    "business_processes": ["registration"],
                }
            ],
        },
        [],
        pii_map,
        domain_name="CRM",
        parent_cluster_id="component-1",
    )

    assert "governance_package" in package
    assert "semantic_package" in package
    assert "cluster_metadata" in package
    assert "schema_summary" not in package
    assert "columns" not in package
    assert package["governance_package"]["packages"][0]["table_name"] == "customers"
    assert package["cluster_metadata"]["relationships"][0]["join_columns"][0]["source_column"] == "id"


def test_normalize_intelligence_output_maps_v3_fields():
    engine = RelationshipGraphEngine(AsyncMock())
    normalized = engine._normalize_intelligence_output(
        {
            "cluster_summary": "CRM cluster",
            "cluster_confidence": 0.9,
            "entity_graph": [{"from": "customers", "to": "orders"}],
            "business_process_flows": [{"name": "order capture"}],
            "upstream_dependencies": [{"table": "customers"}],
            "downstream_dependencies": [{"table": "orders"}],
            "lifecycle_flows": [{"entity": "customer", "stage": "active"}],
        }
    )
    assert normalized["business_entity_graph"] == normalized["entity_graph"]
    assert normalized["entity_lifecycle_descriptions"] == normalized["lifecycle_flows"]


def test_aggregate_cluster_intelligence_merges_cluster_outputs():
    aggregated = RelationshipGraphEngine._aggregate_cluster_intelligence(
        [
            {
                "cluster_id": "c1",
                "cluster_table_ids": [1],
                "entity_graph": [{"a": 1}],
                "business_process_flows": [{"flow": 1}],
                "upstream_dependencies": [],
                "downstream_dependencies": [{"b": 2}],
                "lifecycle_flows": [{"life": 1}],
            },
            {
                "cluster_id": "c2",
                "cluster_table_ids": [2],
                "entity_graph": [{"a": 2}],
                "business_process_flows": [],
                "upstream_dependencies": [{"c": 3}],
                "downstream_dependencies": [],
                "lifecycle_flows": [],
            },
        ]
    )
    assert len(aggregated["entity_graph"]) == 2
    assert len(aggregated["relationship_intelligence"]["business_process_flows"]) == 1
    assert len(aggregated["cluster_summaries"]) == 2
    assert aggregated["cluster_summaries"][0]["cluster_table_ids"] == [1]
