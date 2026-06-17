from types import SimpleNamespace

from app.services.schema_chunking_service import SchemaChunkingService


def test_schema_chunking_service_uses_instance_helpers() -> None:
    service = SchemaChunkingService()
    database = SimpleNamespace(
        id=1,
        display_name="Demo DB",
        name="demo",
        db_type=SimpleNamespace(value="postgresql"),
        schemas=[
            SimpleNamespace(
                name="public",
                tables=[
                    SimpleNamespace(
                        name="orders",
                        schema=SimpleNamespace(name="public"),
                        table_type=SimpleNamespace(value="table"),
                        description="Orders table",
                        columns=[],
                        relationships_from=[],
                    )
                ],
            )
        ],
    )

    payload = service.build(database)

    assert payload["database_id"] == 1
    assert payload["totals"]["schema_count"] == 1
    assert payload["schema_chunk_count"] == 1


def test_schema_chunking_safe_list_handles_iterables() -> None:
    assert SchemaChunkingService._safe_list((1, 2, 3)) == [1, 2, 3]
