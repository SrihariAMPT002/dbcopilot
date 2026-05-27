"""
Unit tests for ConnectionService.

Run with: pytest tests/ -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.api_schemas import ConnectionRequest
from app.models.metadata import DatabaseType, ConnectionStatus


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_request():
    return ConnectionRequest(
        name="test-db",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="testdb",
        username="testuser",
        password="testpass",
    )


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.get = AsyncMock(return_value=None)
    return session


# ── Test: test_connection ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_test_connection_success(sample_request, mock_db_session):
    """test_connection should return success when connector ping succeeds."""
    from app.connectors.base import ConnectionTestResult
    from app.services.connection_service import ConnectionService

    mock_result = ConnectionTestResult(
        success=True,
        message="Connection successful",
        latency_ms=12.5,
        server_version="PostgreSQL 15.0",
        databases_accessible=3,
    )

    with patch("app.services.connection_service.get_connector") as mock_get:
        mock_connector = AsyncMock()
        mock_connector.test_connection = AsyncMock(return_value=mock_result)
        mock_get.return_value = mock_connector

        svc = ConnectionService(mock_db_session)
        result = await svc.test_connection(sample_request)

    assert result.success is True
    assert result.latency_ms == 12.5
    assert "PostgreSQL" in result.server_version


@pytest.mark.asyncio
async def test_test_connection_failure(sample_request, mock_db_session):
    """test_connection should propagate connector failures."""
    from app.connectors.base import ConnectionTestResult
    from app.services.connection_service import ConnectionService

    mock_result = ConnectionTestResult(
        success=False,
        message="Connection refused",
        latency_ms=5001.0,
    )

    with patch("app.services.connection_service.get_connector") as mock_get:
        mock_connector = AsyncMock()
        mock_connector.test_connection = AsyncMock(return_value=mock_result)
        mock_get.return_value = mock_connector

        svc = ConnectionService(mock_db_session)
        result = await svc.test_connection(sample_request)

    assert result.success is False
    assert "refused" in result.message


# ── Test: create_connection ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_connection_new(sample_request, mock_db_session):
    """create_connection should persist a new record with encrypted password."""
    from app.services.connection_service import ConnectionService
    from app.models.metadata import ConnectedDatabase

    # No existing connection with that name
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = None

    created_obj = MagicMock(spec=ConnectedDatabase)
    created_obj.id = 42
    created_obj.name = "test-db"
    created_obj.db_type = "postgresql"
    created_obj.host = "localhost"
    created_obj.port = 5432
    created_obj.database_name = "testdb"
    created_obj.username = "testuser"
    created_obj.status = ConnectionStatus.inactive
    created_obj.schemas = []

    mock_db_session.refresh.side_effect = lambda obj: None

    with patch("app.services.connection_service.encrypt_secret", return_value="ENCRYPTED"):
        with patch.object(
            ConnectionService,
            "create_connection",
            return_value=created_obj,
        ):
            svc = ConnectionService(mock_db_session)
            result = await svc.create_connection(sample_request)

    assert result.id == 42
    assert result.name == "test-db"


@pytest.mark.asyncio
async def test_create_connection_duplicate_raises(sample_request, mock_db_session):
    """create_connection should raise ValueError if name already exists."""
    from app.services.connection_service import ConnectionService
    from app.models.metadata import ConnectedDatabase

    existing = MagicMock(spec=ConnectedDatabase)
    existing.name = "test-db"

    mock_db_session.execute.return_value.scalars.return_value.first.return_value = existing

    svc = ConnectionService(mock_db_session)

    with pytest.raises(ValueError, match="already exists"):
        await svc.create_connection(sample_request)


# ── Test: security helpers ────────────────────────────────────────────────────

def test_encrypt_decrypt_roundtrip():
    """Encrypted value should decrypt back to original."""
    from app.core.security import encrypt_secret, decrypt_secret
    import os

    with patch("app.core.security.settings") as mock_settings:
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        mock_settings.encryption_key = key

        # Reset cipher
        import app.core.security as sec_module
        sec_module._cipher = None

        plaintext = "super_secret_password_123!"
        ciphertext = encrypt_secret(plaintext)
        assert ciphertext != plaintext
        assert len(ciphertext) > 0

        recovered = decrypt_secret(ciphertext)
        assert recovered == plaintext

        # Reset cipher again
        sec_module._cipher = None


def test_mask_secret():
    from app.core.security import mask_secret
    masked = mask_secret("mysecretpassword", visible_chars=3)
    assert masked.startswith("mys")
    assert "****" in masked
    assert "mysecretpassword" not in masked


def test_sanitize_connection_string():
    from app.core.security import sanitize_connection_string
    raw = "postgresql://user:mypassword@localhost:5432/db"
    safe = sanitize_connection_string(raw)
    assert "mypassword" not in safe
    assert "****" in safe
    assert "user" in safe
    assert "localhost" in safe


def test_build_connection_url_encodes_mongodb_credentials():
    from app.core.security import build_connection_url

    url = build_connection_url(
        db_type="mongodb",
        host="mongo.example.com",
        port=27017,
        database="analytics",
        username="user@example.com",
        password="p@ss:word",
    )

    assert "user%40example.com" in url
    assert "p%40ss%3Aword" in url


# ── Test: connector factory ───────────────────────────────────────────────────

def test_get_connector_postgresql():
    from app.connectors import get_connector
    from app.connectors.postgres import PostgresConnector

    c = get_connector(
        db_type="postgresql",
        host="localhost",
        port=5432,
        database="testdb",
        username="user",
        password="pass",
    )
    assert isinstance(c, PostgresConnector)


def test_get_connector_mysql():
    from app.connectors import get_connector
    from app.connectors.mysql import MySQLConnector

    c = get_connector(
        db_type="mysql",
        host="localhost",
        port=3306,
        database="testdb",
        username="user",
        password="pass",
    )
    assert isinstance(c, MySQLConnector)


def test_get_connector_unknown_raises():
    from app.connectors import get_connector

    with pytest.raises(ValueError, match="Unsupported database type"):
        get_connector(
            db_type="oracle",
            host="localhost",
            port=1521,
            database="testdb",
            username="user",
            password="pass",
        )


# ── Test: schema validation ───────────────────────────────────────────────────

def test_connection_request_normalises_db_type():
    req = ConnectionRequest(
        name="test",
        db_type="PostgreSQL",      # mixed case
        host="localhost",
        port=5432,
        database_name="db",
        username="user",
        password="pass",
    )
    assert req.db_type == "postgresql"


def test_connection_request_invalid_port():
    with pytest.raises(Exception):
        ConnectionRequest(
            name="test",
            db_type="postgresql",
            host="localhost",
            port=99999,             # invalid
            database_name="db",
            username="user",
            password="pass",
        )


def test_connection_request_empty_name():
    with pytest.raises(Exception):
        ConnectionRequest(
            name="",                # too short
            db_type="postgresql",
            host="localhost",
            port=5432,
            database_name="db",
            username="user",
            password="pass",
        )
