"""
Asynchronous database connection utilities for DB Copilot.

Provides a unified interface for building connection strings and testing live
connections across PostgreSQL, MySQL, MongoDB, and SQL Server.
"""

from __future__ import annotations

import asyncio
import ssl
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

try:
    import asyncpg
except Exception:  # pragma: no cover - optional dependency
    asyncpg = None

try:
    import aiomysql
except Exception:  # pragma: no cover - optional dependency
    aiomysql = None

try:
    import motor.motor_asyncio as motor
except Exception:  # pragma: no cover - optional dependency
    motor = None

try:
    import aioodbc
except Exception:  # pragma: no cover - optional dependency
    aioodbc = None

try:
    from sqlalchemy.engine import URL
except Exception:  # pragma: no cover - optional dependency
    URL = None


SUPPORTED_DB_TYPES = {"postgresql", "mysql", "mongodb", "sqlserver"}


@dataclass(slots=True)
class ConnectionResult:
    success: bool
    message: str
    db_type: str
    connection_string: str
    latency_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


class ConnectionUtilityError(ValueError):
    """Raised when the supplied database type or configuration is invalid."""


def _normalize_db_type(db_type: str) -> str:
    value = (db_type or "").strip().lower()
    if value not in SUPPORTED_DB_TYPES:
        supported = ", ".join(sorted(SUPPORTED_DB_TYPES))
        raise ConnectionUtilityError(
            f"Unsupported database type: {db_type!r}. Supported types: {supported}"
        )
    return value


def _get_config_value(config: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in config and config[key] not in (None, ""):
            return config[key]
    return default


def _require_value(config: Dict[str, Any], *keys: str, field_name: str) -> Any:
    value = _get_config_value(config, *keys)
    if value in (None, ""):
        raise ConnectionUtilityError(f"Missing required field: {field_name}")
    return value


def _parse_port(value: Any, default: int) -> int:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ConnectionUtilityError(f"Invalid port value: {value!r}") from exc


def _build_ssl_context(cert_path: str) -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=cert_path)
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    return context


def _build_postgres_connection_string(config: Dict[str, Any]) -> str:
    host = _require_value(config, "host", field_name="host")
    port = _parse_port(config.get("port"), 5432)
    username = _require_value(config, "username", field_name="username")
    password = _require_value(config, "password", field_name="password")
    database_name = _require_value(config, "database_name", "database", field_name="database_name")

    if URL is None:
        return (
            f"postgresql://{username}:{password}@{host}:{port}/{database_name}"
        )

    return str(
        URL.create(
            drivername="postgresql+asyncpg",
            username=username,
            password=password,
            host=host,
            port=port,
            database=database_name,
        )
    )


def _build_mysql_connection_string(config: Dict[str, Any]) -> str:
    host = _require_value(config, "host", field_name="host")
    port = _parse_port(config.get("port"), 3306)
    username = _require_value(config, "username", field_name="username")
    password = _require_value(config, "password", field_name="password")
    database_name = _require_value(config, "database_name", "database", field_name="database_name")

    if URL is None:
        return f"mysql+aiomysql://{username}:{password}@{host}:{port}/{database_name}"

    return str(
        URL.create(
            drivername="mysql+aiomysql",
            username=username,
            password=password,
            host=host,
            port=port,
            database=database_name,
        )
    )


def _build_mongo_connection_string(config: Dict[str, Any]) -> str:
    host = _require_value(config, "host", field_name="host")
    port = _parse_port(config.get("port"), 27017)
    username = _get_config_value(config, "username")
    password = _get_config_value(config, "password")
    database_name = _require_value(config, "database_name", "database", field_name="database_name")

    auth = ""
    if username and password:
        auth = f"{username}:{password}@"

    return f"mongodb://{auth}{host}:{port}/{database_name}"


def _build_sqlserver_connection_string(config: Dict[str, Any]) -> str:
    host = _require_value(config, "host", field_name="host")
    port = _parse_port(config.get("port"), 1433)
    username = _require_value(config, "username", field_name="username")
    password = _require_value(config, "password", field_name="password")
    database_name = _require_value(config, "database_name", "database", field_name="database_name")

    encrypt = "Encrypt=yes;" if bool(config.get("ssl_enabled", False)) else "Encrypt=no;"
    trust_server_certificate = "TrustServerCertificate=no;" if bool(config.get("ssl_enabled", False)) else "TrustServerCertificate=yes;"
    return (
        "Driver={ODBC Driver 17 for SQL Server};"
        f"Server={host},{port};"
        f"Database={database_name};"
        f"UID={username};"
        f"PWD={password};"
        f"{encrypt}"
        f"{trust_server_certificate}"
    )


def build_connection_string(db_type: str, config: Dict[str, Any]) -> str:
    """
    Build a driver-appropriate connection string for the given database type.
    """

    normalized = _normalize_db_type(db_type)
    if normalized == "postgresql":
        return _build_postgres_connection_string(config)
    if normalized == "mysql":
        return _build_mysql_connection_string(config)
    if normalized == "mongodb":
        return _build_mongo_connection_string(config)
    if normalized == "sqlserver":
        return _build_sqlserver_connection_string(config)
    raise ConnectionUtilityError(f"Unsupported database type: {db_type!r}")


def _friendly_error(db_type: str, exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    lowered = message.lower()

    if any(term in lowered for term in ("authentication", "password authentication failed", "access denied", "login failed")):
        return f"Auth Failure: {message}"
    if any(term in lowered for term in ("timeout", "timed out", "time out")):
        return f"Timeout: {message}"
    if any(term in lowered for term in ("certificate", "tls", "ssl", "handshake", "ca file", "cert")):
        return f"Invalid Cert: {message}"
    if any(term in lowered for term in ("could not connect", "connection refused", "network", "name or service not known", "host not found")):
        return f"Connection Failed: {message}"

    return f"{db_type.title()} connection failed: {message}"


def _build_ssl_kwargs(db_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
    if not bool(config.get("ssl_enabled", False)):
        return {}

    cert_path = _get_config_value(config, "ssl_cert_path")
    if db_type == "postgresql":
        if cert_path:
            return {"ssl": _build_ssl_context(cert_path)}
        return {"ssl": "require"}

    if db_type == "mysql":
        if cert_path:
            return {"ssl": _build_ssl_context(cert_path)}
        return {"ssl": ssl.create_default_context()}

    if db_type == "mongodb":
        if cert_path:
            return {"tls": True, "tlsCAFile": cert_path}
        return {"tls": True}

    if db_type == "sqlserver":
        # ODBC driver SSL is configured in the DSN string.
        return {}

    return {}


async def _test_postgresql(config: Dict[str, Any]) -> Dict[str, Any]:
    if asyncpg is None:
        raise ConnectionUtilityError("asyncpg is required for PostgreSQL connections")

    conn_kwargs: Dict[str, Any] = {
        "host": _require_value(config, "host", field_name="host"),
        "port": _parse_port(config.get("port"), 5432),
        "user": _require_value(config, "username", field_name="username"),
        "password": _require_value(config, "password", field_name="password"),
        "database": _require_value(config, "database_name", "database", field_name="database_name"),
        "timeout": int(config.get("timeout", 30)),
    }
    conn_kwargs.update(_build_ssl_kwargs("postgresql", config))

    conn = await asyncpg.connect(**conn_kwargs)
    try:
        version = await conn.fetchval("SELECT version()")
        return {"server_version": version or "PostgreSQL", "session": conn}
    except Exception:
        await conn.close()
        raise


async def _test_mysql(config: Dict[str, Any]) -> Dict[str, Any]:
    if aiomysql is None:
        raise ConnectionUtilityError("aiomysql is required for MySQL connections")

    conn_kwargs: Dict[str, Any] = {
        "host": _require_value(config, "host", field_name="host"),
        "port": _parse_port(config.get("port"), 3306),
        "user": _require_value(config, "username", field_name="username"),
        "password": _require_value(config, "password", field_name="password"),
        "db": _require_value(config, "database_name", "database", field_name="database_name"),
        "connect_timeout": int(config.get("timeout", 30)),
        "autocommit": True,
    }
    conn_kwargs.update(_build_ssl_kwargs("mysql", config))

    conn = await aiomysql.connect(**conn_kwargs)
    try:
        async with conn.cursor() as cur:
            await cur.execute("SELECT VERSION()")
            row = await cur.fetchone()
        version = row[0] if row else "MySQL"
        return {"server_version": version, "session": conn}
    except Exception:
        conn.close()
        await conn.wait_closed()
        raise


async def _test_mongodb(config: Dict[str, Any]) -> Dict[str, Any]:
    if motor is None:
        raise ConnectionUtilityError("motor is required for MongoDB connections")

    host = _require_value(config, "host", field_name="host")
    port = _parse_port(config.get("port"), 27017)
    username = _get_config_value(config, "username")
    password = _get_config_value(config, "password")
    database_name = _require_value(config, "database_name", "database", field_name="database_name")

    uri_auth = ""
    if username and password:
        uri_auth = f"{username}:{password}@"

    uri = f"mongodb://{uri_auth}{host}:{port}/{database_name}"
    client_kwargs = {
        "serverSelectionTimeoutMS": int(config.get("timeout_ms", 5000)),
        "uuidRepresentation": "standard",
    }
    client_kwargs.update(_build_ssl_kwargs("mongodb", config))

    client = motor.AsyncIOMotorClient(uri, **client_kwargs)
    try:
        await client.admin.command("ping")
        db = client[database_name]
        version = await db.command("buildInfo")
        return {"server_version": version.get("version", "MongoDB"), "session": client}
    except Exception:
        client.close()
        raise


async def _test_sqlserver(config: Dict[str, Any]) -> Dict[str, Any]:
    if aioodbc is None:
        raise ConnectionUtilityError("aioodbc is required for SQL Server connections")

    dsn = build_connection_string("sqlserver", config)
    loop = asyncio.get_running_loop()
    conn = await aioodbc.connect(dsn=dsn, loop=loop)
    try:
        async with conn.cursor() as cur:
            await cur.execute("SELECT @@VERSION")
            row = await cur.fetchone()
        version = row[0] if row else "SQL Server"
        return {"server_version": version, "session": conn}
    except Exception:
        conn.close()
        raise


async def test_connection(db_type: str, config: Dict[str, Any]) -> ConnectionResult:
    """
    Attempt a live connection and return a detailed result object.

    The result includes a user-friendly message that can be shown directly in
    the frontend.
    """

    normalized = _normalize_db_type(db_type)
    connection_string = build_connection_string(normalized, config)
    start = time.perf_counter()

    try:
        if normalized == "postgresql":
            payload = await _test_postgresql(config)
        elif normalized == "mysql":
            payload = await _test_mysql(config)
        elif normalized == "mongodb":
            payload = await _test_mongodb(config)
        elif normalized == "sqlserver":
            payload = await _test_sqlserver(config)
        else:  # pragma: no cover - protected by normalization
            raise ConnectionUtilityError(f"Unsupported database type: {db_type!r}")

        latency_ms = (time.perf_counter() - start) * 1000
        session = payload.get("session")
        if session is not None:
            # Close transient validation sessions to avoid leaking connections.
            if normalized == "postgresql":
                await session.close()
            elif normalized == "mysql":
                session.close()
                await session.wait_closed()
            elif normalized == "mongodb":
                session.close()
            elif normalized == "sqlserver":
                session.close()

        return ConnectionResult(
            success=True,
            message=f"{normalized.title()} connection successful",
            db_type=normalized,
            connection_string=connection_string,
            latency_ms=latency_ms,
            details={
                "server_version": payload.get("server_version"),
            },
        )
    except ConnectionUtilityError as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        return ConnectionResult(
            success=False,
            message=str(exc),
            db_type=normalized,
            connection_string=connection_string,
            latency_ms=latency_ms,
        )
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        return ConnectionResult(
            success=False,
            message=_friendly_error(normalized, exc),
            db_type=normalized,
            connection_string=connection_string,
            latency_ms=latency_ms,
            details={"error_type": exc.__class__.__name__},
        )

