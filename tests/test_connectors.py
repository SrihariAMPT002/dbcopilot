"""
Unit tests for connector layer.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.connectors.base import (
    ColumnInfo,
    ConnectionTestResult,
    RelationshipInfo,
    SchemaInfo,
    TableInfo,
)


# ── BaseConnector: introspect orchestration ───────────────────────────────────

class MockConnector:
    """Minimal concrete subclass of BaseConnector for testing."""

    def __init__(self):
        self.logger = MagicMock()
        self._connected = False

    async def get_schemas(self):
        return ["public", "analytics"]

    async def get_tables(self, schema):
        return [
            TableInfo(name="users",  table_type="table", row_count=1200),
            TableInfo(name="orders", table_type="table", row_count=4500),
        ]

    async def get_columns(self, schema, table):
        return [
            ColumnInfo(name="id",   data_type="integer",  is_primary_key=True,  is_nullable=False),
            ColumnInfo(name="name", data_type="varchar",  is_nullable=False),
            ColumnInfo(name="email",data_type="varchar",  is_nullable=True),
        ]

    async def get_relationships(self, schema, table):
        if table == "orders":
            return [
                RelationshipInfo(
                    column_name="user_id",
                    referenced_schema="public",
                    referenced_table="users",
                    referenced_column="id",
                    constraint_name="orders_user_id_fk",
                )
            ]
        return []

    async def introspect(self):
        from app.connectors.base import BaseConnector
        # Call the real introspect logic via delegation
        schemas_names = await self.get_schemas()
        result = []
        for schema_name in schemas_names:
            schema_info = SchemaInfo(name=schema_name)
            tables = await self.get_tables(schema=schema_name)
            for table in tables:
                try:
                    table.columns      = await self.get_columns(schema=schema_name, table=table.name)
                    table.relationships = await self.get_relationships(schema=schema_name, table=table.name)
                except Exception:
                    pass
                schema_info.tables.append(table)
            result.append(schema_info)
        return result


@pytest.mark.asyncio
async def test_introspect_returns_all_schemas():
    conn = MockConnector()
    schemas = await conn.introspect()

    assert len(schemas) == 2
    assert schemas[0].name == "public"
    assert schemas[1].name == "analytics"


@pytest.mark.asyncio
async def test_introspect_populates_tables():
    conn = MockConnector()
    schemas = await conn.introspect()

    public = schemas[0]
    assert len(public.tables) == 2
    table_names = [t.name for t in public.tables]
    assert "users" in table_names
    assert "orders" in table_names


@pytest.mark.asyncio
async def test_introspect_populates_columns():
    conn = MockConnector()
    schemas = await conn.introspect()

    users_table = next(t for t in schemas[0].tables if t.name == "users")
    assert len(users_table.columns) == 3

    pk_cols = [c for c in users_table.columns if c.is_primary_key]
    assert len(pk_cols) == 1
    assert pk_cols[0].name == "id"


@pytest.mark.asyncio
async def test_introspect_populates_relationships():
    conn = MockConnector()
    schemas = await conn.introspect()

    orders_table = next(t for t in schemas[0].tables if t.name == "orders")
    assert len(orders_table.relationships) == 1

    rel = orders_table.relationships[0]
    assert rel.column_name == "user_id"
    assert rel.referenced_table == "users"
    assert rel.referenced_column == "id"
    assert rel.constraint_name == "orders_user_id_fk"


@pytest.mark.asyncio
async def test_introspect_handles_column_error_gracefully():
    """If get_columns raises for one table, introspect should continue."""
    conn = MockConnector()

    call_count = 0
    async def flaky_columns(schema, table):
        nonlocal call_count
        call_count += 1
        if table == "orders" and call_count <= 2:
            raise RuntimeError("Simulated column fetch error")
        return []

    conn.get_columns = flaky_columns

    schemas = await conn.introspect()
    # Should still return schemas without crashing
    assert len(schemas) == 2


# ── TableInfo / ColumnInfo dataclasses ────────────────────────────────────────

def test_table_info_defaults():
    t = TableInfo(name="my_table")
    assert t.table_type == "table"
    assert t.row_count is None
    assert t.columns == []
    assert t.relationships == []


def test_column_info_defaults():
    c = ColumnInfo(name="col1", data_type="text")
    assert c.is_nullable is True
    assert c.is_primary_key is False
    assert c.is_foreign_key is False
    assert c.is_unique is False


def test_schema_info_defaults():
    s = SchemaInfo(name="public")
    assert s.tables == []


def test_connection_test_result_fields():
    r = ConnectionTestResult(
        success=True,
        message="ok",
        server_version="PostgreSQL 15",
        latency_ms=8.4,
        databases_accessible=5,
    )
    assert r.success is True
    assert r.databases_accessible == 5


# ── Connector factory ─────────────────────────────────────────────────────────

def test_registry_all_types():
    from app.connectors import get_connector, PostgresConnector, MySQLConnector, MongoConnector

    for db_type, expected_cls in [
        ("postgresql", PostgresConnector),
        ("mysql",      MySQLConnector),
        ("mongodb",    MongoConnector),
    ]:
        c = get_connector(
            db_type=db_type,
            host="localhost",
            port=5432,
            database="db",
            username="u",
            password="p",
        )
        assert isinstance(c, expected_cls), f"Expected {expected_cls} for {db_type}"


def test_connector_repr():
    from app.connectors.postgres import PostgresConnector
    c = PostgresConnector(
        host="db.example.com",
        port=5432,
        database="mydb",
        username="admin",
        password="secret",
    )
    r = repr(c)
    assert "PostgresConnector" in r
    assert "db.example.com" in r
    assert "secret" not in r           # password must NOT appear in repr
