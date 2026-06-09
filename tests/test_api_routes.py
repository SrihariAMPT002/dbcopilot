"""
Integration-style tests for FastAPI routes using TestClient.

These tests mock the DB session and service layer so they run
without a real database.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from types import SimpleNamespace

from app.main import app
from app.db.session import get_db


# ── Override the DB dependency ────────────────────────────────────────────────

async def mock_get_db():
    session = AsyncMock()
    session.commit   = AsyncMock()
    session.rollback = AsyncMock()
    session.close    = AsyncMock()
    yield session


app.dependency_overrides[get_db] = mock_get_db


@pytest.fixture(scope="module")
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ── Health check ──────────────────────────────────────────────────────────────

def test_health_endpoint(client):
    with patch("app.main.check_db_health", return_value=True):
        r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert "version" in body
    assert "db_healthy" in body


def test_root_endpoint(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert "app" in body
    assert "docs" in body


# ── POST /api/v1/connections/test ─────────────────────────────────────────────

def test_test_connection_endpoint_success(client):
    from app.connectors.base import ConnectionTestResult

    mock_result = ConnectionTestResult(
        success=True,
        message="Connection successful",
        latency_ms=14.2,
        server_version="PostgreSQL 15.3",
        databases_accessible=2,
    )

    with patch("app.services.connection_service.get_connector") as mock_get:
        mock_conn = AsyncMock()
        mock_conn.test_connection = AsyncMock(return_value=mock_result)
        mock_get.return_value = mock_conn

        r = client.post("/api/v1/connections/test", json={
            "name": "my-db",
            "db_type": "postgresql",
            "host": "localhost",
            "port": 5432,
            "database_name": "testdb",
            "username": "admin",
            "password": "password123",
        })

    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["latency_ms"] == 14.2


def test_test_connection_endpoint_missing_fields(client):
    """Validation error when required fields are missing."""
    r = client.post("/api/v1/connections/test", json={
        "db_type": "postgresql",
        # missing: name, host, port, database_name, username, password
    })
    assert r.status_code == 422


def test_test_connection_endpoint_invalid_db_type(client):
    r = client.post("/api/v1/connections/test", json={
        "name": "x",
        "db_type": "oracle",          # not supported
        "host": "localhost",
        "port": 1521,
        "database_name": "db",
        "username": "u",
        "password": "p",
    })
    assert r.status_code == 422


# ── GET /api/v1/connections ───────────────────────────────────────────────────

def test_list_connections_empty(client):
    with patch(
        "app.services.connection_service.ConnectionService.list_connections",
        new_callable=AsyncMock,
        return_value=[],
    ):
        r = client.get("/api/v1/connections")
    assert r.status_code == 200
    assert r.json() == []


# ── POST /api/v1/connections ──────────────────────────────────────────────────

def test_create_connection_conflict(client):
    """409 when a connection with that name already exists."""
    with patch(
        "app.services.connection_service.ConnectionService.create_connection",
        new_callable=AsyncMock,
        side_effect=ValueError("A connection named 'my-db' already exists."),
    ):
        r = client.post("/api/v1/connections", json={
            "name": "my-db",
            "db_type": "postgresql",
            "host": "localhost",
            "port": 5432,
            "database_name": "db",
            "username": "u",
            "password": "p",
        })
    assert r.status_code == 409
    assert "already exists" in r.json()["detail"]


# ── GET /api/v1/connections/{db_id} ──────────────────────────────────────────

def test_get_connection_not_found(client):
    with patch(
        "app.services.connection_service.ConnectionService.get_connection",
        new_callable=AsyncMock,
        return_value=None,
    ):
        r = client.get("/api/v1/connections/9999")
    assert r.status_code == 404


# ── DELETE /api/v1/connections/{db_id} ───────────────────────────────────────

def test_delete_connection_not_found(client):
    with patch(
        "app.services.connection_service.ConnectionService.delete_connection",
        new_callable=AsyncMock,
        return_value=False,
    ):
        r = client.delete("/api/v1/connections/9999")
    assert r.status_code == 404


def test_delete_connection_success(client):
    with patch(
        "app.services.connection_service.ConnectionService.delete_connection",
        new_callable=AsyncMock,
        return_value=True,
    ):
        r = client.delete("/api/v1/connections/1")
    assert r.status_code == 200
    assert r.json()["success"] is True


# ── AI placeholders ───────────────────────────────────────────────────────────

def test_chat_placeholder(client):
    r = client.post("/api/v1/ai/chat", json={
        "db_id": 1,
        "message": "How many users do we have?",
    })
    assert r.status_code == 200
    body = r.json()
    assert "coming soon" in body["message"].lower() or "not yet" in body["message"].lower()


def test_generate_sql_placeholder(client):
    r = client.post("/api/v1/ai/generate-sql", json={
        "db_id": 1,
        "natural_language_query": "Show me total revenue by month",
    })
    assert r.status_code == 200


def test_readiness_endpoint_includes_category_scores(client):
    fake_breakdown = SimpleNamespace(
        database_id=1,
        database_name="Demo DB",
        readiness_status=SimpleNamespace(value="READY"),
        generated_at=datetime.now(timezone.utc),
        metadata_score=95,
        semantic_score=92,
        embeddings_score=88,
        relationship_score=90,
        prompt_score=85,
        overall_score=92,
        metadata_readiness_score=95,
        semantic_readiness_score=92,
        relationship_readiness_score=90,
        ai_context_readiness_score=88,
        governance_readiness_score=85,
        category_scores={
            "metadata_readiness_score": 95,
            "semantic_readiness_score": 92,
            "relationship_readiness_score": 90,
            "ai_context_readiness_score": 88,
            "governance_readiness_score": 85,
            "overall_score": 92,
        },
        missing_stages=[],
        remediation_hints=[],
        details={},
    )

    with patch(
        "app.api.routes.readiness.ReadinessService.get_or_compute",
        new_callable=AsyncMock,
        return_value=fake_breakdown,
    ):
        r = client.get("/api/v1/readiness/1")

    assert r.status_code == 200
    body = r.json()
    assert "category_scores" in body
    assert body["category_scores"]["ai_context_readiness_score"] == 88
    assert body["scores"]["overall_score"] == 92


# ── OpenAPI docs ──────────────────────────────────────────────────────────────

def test_openapi_schema_accessible(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert schema["info"]["title"] == "DB Copilot"


def test_docs_accessible(client):
    r = client.get("/docs")
    assert r.status_code == 200
