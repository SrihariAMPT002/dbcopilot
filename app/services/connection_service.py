"""
ConnectionService — manages the lifecycle of external database connections.

Responsibilities:
  - Validate & test credentials
  - Persist ConnectedDatabase records
  - Encrypt/decrypt passwords
  - Query metadata for API responses
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.connectors import get_connector
from app.core.security import decrypt_secret, encrypt_secret
from app.models.metadata import (
    ConnectedDatabase,
    ConnectionStatus,
    DatabaseColumn,
    DatabaseRelationship,
    DatabaseSchema,
    DatabaseTable,
)
from app.schemas.api_schemas import (
    ConnectionRequest,
    ConnectionSummary,
    TestConnectionResponse,
)
from app.utils import safe_flush

logger = logging.getLogger(__name__)


class ConnectionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Test connection (does NOT persist) ─────────────────────────────────

    async def test_connection(self, req: ConnectionRequest) -> TestConnectionResponse:
        """Verify credentials by doing a live ping — nothing is stored."""
        connector = get_connector(
            db_type=req.db_type,
            host=req.host,
            port=req.port,
            database=req.database_name,
            username=req.username,
            password=req.password,
            ssl_enabled=req.ssl_enabled,
        )
        result = await connector.test_connection()
        return TestConnectionResponse(
            success=result.success,
            message=result.message,
            latency_ms=result.latency_ms,
            server_version=result.server_version,
            databases_accessible=result.databases_accessible,
        )

    # ── Create connection ──────────────────────────────────────────────────

    async def create_connection(self, req: ConnectionRequest) -> ConnectedDatabase:
        """
        Persist a new connected database record.
        Password is encrypted at rest.
        """
        # Check for duplicate name
        existing = await self.db.execute(
            select(ConnectedDatabase).where(ConnectedDatabase.name == req.name)
        )
        if existing.scalars().first():
            raise ValueError(f"A connection named '{req.name}' already exists.")

        encrypted_pw = encrypt_secret(req.password)

        db_conn = ConnectedDatabase(
            name=req.name,
            db_type=req.db_type,
            host=req.host,
            port=req.port,
            database_name=req.database_name,
            username=req.username,
            encrypted_password=encrypted_pw,
            ssl_enabled=req.ssl_enabled,
            status=ConnectionStatus.inactive,
        )
        self.db.add(db_conn)
        await safe_flush(self.db)
        await self.db.refresh(db_conn)
        logger.info("Created connection record id=%s name=%r", db_conn.id, db_conn.name)
        return db_conn

    # ── Get all connections ────────────────────────────────────────────────

    async def list_connections(self) -> List[ConnectionSummary]:
        """
        Retrieve all connections with eager-loaded schemas and tables.
        Converts to Pydantic inside session to avoid lazy-loading issues.
        """
        result = await self.db.execute(
            select(ConnectedDatabase)
            .options(
                selectinload(ConnectedDatabase.schemas)
                .selectinload(DatabaseSchema.tables)
            )
            .order_by(ConnectedDatabase.created_at.desc())
        )
        connections = result.scalars().unique().all()
        
        # Convert to DTO inside session (before expiration)
        summaries = []
        for conn in connections:
            schema_count = len(conn.schemas) if conn.schemas else 0
            table_count = sum(len(s.tables) for s in (conn.schemas or [])) if conn.schemas else 0
            summaries.append(
                self.to_summary(conn, schema_count=schema_count, table_count=table_count)
            )
        return summaries

    # ── Get single connection ──────────────────────────────────────────────

    async def get_connection(self, db_id: int) -> Optional[ConnectionSummary]:
        """
        Retrieve a single connection with eager-loaded schemas and tables.
        Returns Pydantic DTO (not raw ORM) to avoid lazy-loading after session closes.
        """
        result = await self.db.execute(
            select(ConnectedDatabase)
            .options(
                selectinload(ConnectedDatabase.schemas)
                .selectinload(DatabaseSchema.tables)
                .selectinload(DatabaseTable.columns)
            )
            .where(ConnectedDatabase.id == db_id)
        )
        conn = result.scalars().first()
        if not conn:
            return None
        
        # Convert to DTO inside session
        schema_count = len(conn.schemas) if conn.schemas else 0
        table_count = sum(len(s.tables) for s in (conn.schemas or [])) if conn.schemas else 0
        return self.to_summary(conn, schema_count=schema_count, table_count=table_count)

    # ── Delete connection ──────────────────────────────────────────────────

    async def delete_connection(self, db_id: int) -> bool:
        conn = await self.db.get(ConnectedDatabase, db_id)
        if not conn:
            return False
        await self.db.delete(conn)
        logger.info("Deleted connection id=%s", db_id)
        return True

    # ── Update connection status ───────────────────────────────────────────

    async def update_status(
        self,
        db_id: int,
        status: ConnectionStatus,
        error: Optional[str] = None,
        last_sync_at: Optional[datetime] = None,
    ) -> None:
        conn = await self.db.get(ConnectedDatabase, db_id)
        if conn:
            conn.status = status
            conn.last_error = error
            if last_sync_at:
                conn.last_sync_at = last_sync_at
            await safe_flush(self.db)

    # ── Retrieve decrypted credentials (for sync) ──────────────────────────

    async def get_credentials(self, db_id: int) -> dict:
        conn = await self.db.get(ConnectedDatabase, db_id)
        if not conn:
            raise ValueError(f"Connection id={db_id} not found")
        return {
            "db_type": conn.db_type,
            "host": conn.host,
            "port": conn.port,
            "database": conn.database_name,
            "username": conn.username,
            "password": decrypt_secret(conn.encrypted_password),
        }

    # ── Lightweight summary helper ─────────────────────────────────────────

    @staticmethod
    def to_summary(conn: ConnectedDatabase, schema_count: int = 0, table_count: int = 0) -> ConnectionSummary:
        """
        Convert ORM ConnectedDatabase to Pydantic ConnectionSummary.
        
          IMPORTANT: schema_count and table_count must be precomputed!
        Do NOT access conn.schemas or conn.tables in this method to avoid lazy-loading.
        
        Usage:
            # Inside session:
            schema_count = len(conn.schemas) if conn.schemas is not None else 0
            table_count = sum(len(s.tables) for s in conn.schemas) if conn.schemas else 0
            return ConnectionService.to_summary(conn, schema_count, table_count)
        """
        return ConnectionSummary(
            id=conn.id,
            name=conn.name,
            db_type=conn.db_type.value,
            host=conn.host,
            port=conn.port,
            database_name=conn.database_name,
            username=conn.username,
            ssl_enabled=conn.ssl_enabled,
            status=conn.status.value,
            last_sync_at=conn.last_sync_at,
            created_at=conn.created_at,
            schema_count=schema_count,
            table_count=table_count,
            last_error=conn.last_error,
        )
