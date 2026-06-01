"""
Connector factory — instantiate the right connector for a given db_type.

Usage:
    connector = get_connector(db_type="postgresql", host=..., ...)
    async with connector:
        schemas = await connector.introspect()
"""

from typing import Any

from app.connectors.base import BaseConnector
from app.connectors.base_nosql import BaseNoSQLConnector
from app.connectors.connection_utils import (
    ConnectionResult,
    ConnectionUtilityError,
    build_connection_string,
    test_connection,
)
from app.connectors.postgres import PostgresConnector
from app.connectors.mysql import MySQLConnector
from app.connectors.sqlserver import SQLServerConnector
from app.connectors.mongo import MongoConnector

_REGISTRY: dict = {
    "postgresql": PostgresConnector,
    "mysql": MySQLConnector,
    "sqlserver": SQLServerConnector,
    "mongodb": MongoConnector,
}


def get_connector(db_type: str, **kwargs: Any) -> BaseConnector:
    """
    Return an instantiated connector for the given database type.

    Args:
        db_type: one of 'postgresql', 'mysql', 'sqlserver', 'mongodb'
        **kwargs: forwarded to the connector __init__
                  (host, port, database, username, password, timeout, …)

    Raises:
        ValueError: if db_type is not supported
    """
    key = db_type.lower().strip()
    cls = _REGISTRY.get(key)
    if cls is None:
        supported = ", ".join(sorted(_REGISTRY.keys()))
        raise ValueError(
            f"Unsupported database type: {db_type!r}. "
            f"Supported types: {supported}"
        )
    return cls(**kwargs)


__all__ = [
    "get_connector",
    "BaseConnector",
    "BaseNoSQLConnector",
    "PostgresConnector",
    "MySQLConnector",
    "SQLServerConnector",
    "MongoConnector",
    "ConnectionResult",
    "ConnectionUtilityError",
    "build_connection_string",
    "test_connection",
]
