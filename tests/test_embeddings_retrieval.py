"""
Tests for the Embeddings & Retrieval module.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.services.qdrant_service import QdrantService


async def _mock_get_db():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    yield session


app.dependency_overrides[get_db] = _mock_get_db


@pytest.fixture(scope="module")
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_generate_embeddings_route_returns_success(client):
    fake_result = SimpleNamespace(
        database_id=1,
        database_name="Demo DB",
        embedding_model="text-embedding-3-small",
        tables_indexed=2,
        vectors_indexed=6,
        token_usage={"input_tokens": 10, "output_tokens": 0, "total_tokens": 10},
        latency_ms=123.4,
        success=True,
        message="Indexed 2 tables into 6 vectors",
    )

    fake_engine = MagicMock()
    fake_engine.is_embedding_ready.return_value = True
    fake_engine.is_qdrant_ready.return_value = True
    fake_engine.generate_database_embeddings = AsyncMock(return_value=fake_result)

    with patch("app.api.routes.embeddings.EmbeddingEngine", return_value=fake_engine):
        response = client.post("/api/v1/embeddings/generate/1")

    assert response.status_code == 200
    body = response.json()
    assert body["database_id"] == 1
    assert body["tables_indexed"] == 2
    assert body["vectors_indexed"] == 6
    assert body["success"] is True


def test_delete_embeddings_route_returns_204(client):
    fake_engine = MagicMock()
    fake_engine._fetch_database = AsyncMock(return_value=SimpleNamespace(id=1))
    fake_qdrant = MagicMock()
    fake_qdrant.delete_by_database = MagicMock()

    db_session = AsyncMock()
    db_session.execute = AsyncMock(return_value=MagicMock())

    with (
        patch("app.api.routes.embeddings.EmbeddingEngine", return_value=fake_engine),
        patch("app.api.routes.embeddings.get_qdrant_service", return_value=fake_qdrant),
        patch("app.api.routes.embeddings.safe_flush", new=AsyncMock()),
    ):
        response = client.delete("/api/v1/embeddings/1")

    assert response.status_code == 204
    fake_qdrant.delete_by_database.assert_called_once_with(1)


def test_semantic_search_normalizes_relationship_payload(client):
    fake_engine = MagicMock()
    fake_engine.is_embedding_ready.return_value = True
    fake_engine.is_qdrant_ready.return_value = True
    fake_engine._embed_text = AsyncMock(return_value=([0.1, 0.2, 0.3], {}))

    fake_qdrant = MagicMock()
    fake_qdrant.search_all_collections.return_value = [
        {
            "score": 0.91,
            "database_id": 1,
            "database_name": "Demo DB",
            "schema_name": "public",
            "table_name": "orders",
            "table_type": "table",
            "text": "Orders table with customer references.",
            "semantic_summary": "Order facts",
            "column_names": ["id", "customer_id"],
            "relationships": [
                {
                    "column_name": "customer_id",
                    "referenced_schema": "public",
                    "referenced_table_name": "customers",
                    "referenced_column_name": "id",
                    "constraint_name": "fk_orders_customer",
                }
            ],
            "collection_name": "schema_tables",
            "_collection": "schema_tables",
        }
    ]

    with (
        patch("app.api.routes.embeddings.EmbeddingEngine", return_value=fake_engine),
        patch("app.api.routes.embeddings.get_qdrant_service", return_value=fake_qdrant),
    ):
        response = client.post(
            "/api/v1/embeddings/search",
            json={"db_id": 1, "query": "customer revenue", "top_k": 5, "collection": "all"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total_hits"] == 1
    assert body["results"][0]["relationships"] == [
        "customer_id -> public.customers.id (fk_orders_customer)"
    ]


def test_qdrant_service_search_all_collections_merges_hits():
    class FakeClient:
        def search(self, collection_name, query_vector, query_filter=None, limit=5, with_payload=True):
            return [
                SimpleNamespace(
                    score=0.8,
                    payload={
                        "database_id": 1,
                        "table_id": 11,
                        "schema_id": 2,
                        "schema_name": "public",
                        "table_name": f"{collection_name}_table",
                        "table_type": "table",
                        "text": f"{collection_name} text",
                        "column_names": ["id"],
                        "relationships": [],
                        "collection_name": collection_name,
                    },
                )
            ]

    service = QdrantService.__new__(QdrantService)
    service.client = FakeClient()

    results = service.search_all_collections(query_vector=[0.1, 0.2], db_id=1, top_k_per_collection=1)

    assert len(results) == 3
    assert {item["_collection"] for item in results} == {
        "schema_tables",
        "schema_relationships",
        "schema_prompts",
    }
