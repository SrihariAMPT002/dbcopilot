from app.schema_engine.relationship_graph import (
    ExportBundle,
    GraphEdgeRecord,
    GraphMetrics,
    GraphNodeRecord,
    JoinColumnLink,
    RelationshipGraphEngine,
    RelationshipGraphSnapshot,
)


def test_export_graph_formats():
    snapshot = RelationshipGraphSnapshot(
        database_id=7,
        database_name="analytics",
        generated_at=None,  # type: ignore[arg-type]
        nodes=[
            GraphNodeRecord(
                table_id=1,
                schema_id=10,
                schema_name="public",
                table_name="users",
                table_type="table",
                degree=1,
                in_degree=0,
                out_degree=1,
                depth=0,
                is_isolated=False,
            )
        ],
        edges=[
            GraphEdgeRecord(
                source_table_id=1,
                target_table_id=2,
                source_table_name="users",
                target_table_name="orders",
                source_schema_name="public",
                target_schema_name="public",
                relationship_type="fk",
                join_columns=[JoinColumnLink(source_column="id", target_column="user_id")],
                relationship_strength=1.0,
                path_depth=1,
                is_circular=False,
            )
        ],
        metrics=GraphMetrics(
            table_count=2,
            edge_count=1,
            relationship_density=1.0,
            graph_depth=1,
            central_tables=["public.users"],
            isolated_tables=[],
            cycle_count=0,
        ),
        cycles=[],
    )

    engine = RelationshipGraphEngine(db=None)  # type: ignore[arg-type]

    json_bundle = engine.export_graph(snapshot, "json")
    assert json_bundle.filename.endswith(".json")
    assert '"database_name": "analytics"' in json_bundle.content

    md_bundle = engine.export_graph(snapshot, "markdown")
    assert md_bundle.filename.endswith(".md")
    assert "# Relationship Graph: analytics" in md_bundle.content

    diagram_bundle = engine.export_graph(snapshot, "diagram")
    assert diagram_bundle.filename.endswith(".mmd")
    assert "graph TD" in diagram_bundle.content
    assert "T1" in diagram_bundle.content


def test_normalize_step_handles_reverse_traversal():
    engine = RelationshipGraphEngine(db=None)  # type: ignore[arg-type]
    edge = GraphEdgeRecord(
        source_table_id=1,
        target_table_id=2,
        source_table_name="users",
        target_table_name="orders",
        source_schema_name="public",
        target_schema_name="public",
        relationship_type="fk",
        join_columns=[JoinColumnLink(source_column="id", target_column="user_id")],
        relationship_strength=1.0,
        path_depth=1,
        is_circular=False,
    )

    step = engine._normalize_step(edge, from_table=2, to_table=1)
    assert step.relationship_type == "fk_reversed"
    assert step.join_columns[0].source_column == "user_id"
    assert step.join_columns[0].target_column == "id"
