"""
ConnectionService — manages the lifecycle of external database connections.

Responsibilities:
  - Validate & test credentials
  - Persist ConnectedDatabase records
  - Encrypt/decrypt passwords
  - Query metadata for API responses
"""

import logging
import json
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.connectors import get_connector
from app.core.security import decrypt_secret, encrypt_secret
from app.models.metadata import (
    ConnectedDatabase,
    ConnectionStatus,
    DatabaseLifecycleEvent,
    DatabaseLifecycleStatus,
    DatabaseColumn,
    DatabaseRelationship,
    DatabaseSchema,
    DatabaseTable,
)
from app.schemas.api_schemas import (
    ConnectionRequest,
    ConnectionLifecycleResponse,
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
            lifecycle_status=DatabaseLifecycleStatus.active,
        )
        self.db.add(db_conn)
        await safe_flush(self.db)
        await self.db.refresh(db_conn)
        logger.info("Created connection record id=%s name=%r", db_conn.id, db_conn.name)
        return db_conn

    # ── Get all connections ────────────────────────────────────────────────

    async def list_connections(self, include_archived: bool = False) -> List[ConnectionSummary]:
        """
        Retrieve all connections with eager-loaded schemas and tables.
        Converts to Pydantic inside session to avoid lazy-loading issues.
        """
        stmt = select(ConnectedDatabase).options(
            selectinload(ConnectedDatabase.schemas).selectinload(DatabaseSchema.tables)
        )
        if not include_archived:
            stmt = stmt.where(ConnectedDatabase.lifecycle_status != DatabaseLifecycleStatus.archived)
        result = await self.db.execute(stmt.order_by(ConnectedDatabase.created_at.desc()))
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

    async def _get_connection_or_none(self, db_id: int) -> Optional[ConnectedDatabase]:
        result = await self.db.execute(
            select(ConnectedDatabase)
            .options(
                selectinload(ConnectedDatabase.schemas)
                .selectinload(DatabaseSchema.tables)
                .selectinload(DatabaseTable.columns)
            )
            .where(ConnectedDatabase.id == db_id)
        )
        return result.scalars().first()

    async def _record_lifecycle_event(
        self,
        conn: ConnectedDatabase,
        *,
        event_type: str,
        actor: Optional[str] = None,
        reason: Optional[str] = None,
        trace_id: Optional[str] = None,
        metadata_json: Optional[str] = None,
    ) -> None:
        self.db.add(
            DatabaseLifecycleEvent(
                connected_db_id=conn.id,
                event_type=event_type,
                actor=actor,
                reason=reason,
                trace_id=trace_id,
                metadata_json=metadata_json,
            )
        )

    async def _count_related_resources(self, db_id: int) -> dict[str, int]:
        schema_count = await self.db.scalar(
            select(func.count(DatabaseSchema.id)).where(DatabaseSchema.connected_db_id == db_id)
        ) or 0
        table_count = await self.db.scalar(
            select(func.count(DatabaseTable.id))
            .join(DatabaseSchema, DatabaseTable.schema_id == DatabaseSchema.id)
            .where(DatabaseSchema.connected_db_id == db_id)
        ) or 0
        column_count = await self.db.scalar(
            select(func.count(DatabaseColumn.id))
            .join(DatabaseTable, DatabaseColumn.table_id == DatabaseTable.id)
            .join(DatabaseSchema, DatabaseTable.schema_id == DatabaseSchema.id)
            .where(DatabaseSchema.connected_db_id == db_id)
        ) or 0
        relationship_count = await self.db.scalar(
            select(func.count(DatabaseRelationship.id))
            .join(DatabaseTable, DatabaseRelationship.table_id == DatabaseTable.id)
            .join(DatabaseSchema, DatabaseTable.schema_id == DatabaseSchema.id)
            .where(DatabaseSchema.connected_db_id == db_id)
        ) or 0
        return {
            "schemas": int(schema_count),
            "tables": int(table_count),
            "columns": int(column_count),
            "relationships": int(relationship_count),
        }

    async def disconnect_connection(
        self,
        db_id: int,
        *,
        confirmation_text: Optional[str] = None,
        actor: Optional[str] = None,
        reason: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> ConnectionLifecycleResponse:
        conn = await self._get_connection_or_none(db_id)
        if not conn:
            raise ValueError(f"Connection id={db_id} not found")
        if (confirmation_text or "").strip() != conn.name:
            raise ValueError(f"Confirmation text must exactly match connection name '{conn.name}'")
        conn.lifecycle_status = DatabaseLifecycleStatus.disconnected
        conn.status = ConnectionStatus.inactive
        conn.disconnected_at = datetime.now(timezone.utc)
        conn.disconnected_by = actor
        conn.last_error = reason
        await self._record_lifecycle_event(
            conn,
            event_type="DATABASE_DISCONNECTED",
            actor=actor,
            reason=reason,
            trace_id=trace_id,
        )
        await safe_flush(self.db)
        preserved = await self._count_related_resources(db_id)
        return ConnectionLifecycleResponse(
            database_id=conn.id,
            database_name=conn.name,
            lifecycle_status=conn.lifecycle_status.value,
            message="Connection disconnected. Data and intelligence artifacts preserved.",
            preserved_resources=preserved,
            trace_id=trace_id,
        )

    async def reconnect_connection(
        self,
        db_id: int,
        *,
        confirmation_text: Optional[str] = None,
        actor: Optional[str] = None,
        reason: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> ConnectionLifecycleResponse:
        conn = await self._get_connection_or_none(db_id)
        if not conn:
            raise ValueError(f"Connection id={db_id} not found")
        conn.lifecycle_status = DatabaseLifecycleStatus.active
        conn.status = ConnectionStatus.active
        conn.disconnected_at = None
        conn.disconnected_by = None
        conn.archived_at = None
        conn.deleted_at = None
        conn.deletion_summary = None
        conn.last_error = None
        await self._record_lifecycle_event(
            conn,
            event_type="DATABASE_RECONNECTED",
            actor=actor,
            reason=reason,
            trace_id=trace_id,
        )
        await safe_flush(self.db)
        return ConnectionLifecycleResponse(
            database_id=conn.id,
            database_name=conn.name,
            lifecycle_status=conn.lifecycle_status.value,
            message="Connection reconnected.",
            preserved_resources=await self._count_related_resources(db_id),
            trace_id=trace_id,
        )

    async def archive_connection(
        self,
        db_id: int,
        *,
        confirmation_text: Optional[str] = None,
        actor: Optional[str] = None,
        reason: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> ConnectionLifecycleResponse:
        conn = await self._get_connection_or_none(db_id)
        if not conn:
            raise ValueError(f"Connection id={db_id} not found")
        if (confirmation_text or "").strip() != conn.name:
            raise ValueError(f"Confirmation text must exactly match connection name '{conn.name}'")
        conn.lifecycle_status = DatabaseLifecycleStatus.archived
        conn.status = ConnectionStatus.inactive
        conn.archived_at = datetime.now(timezone.utc)
        conn.last_error = reason
        await self._record_lifecycle_event(
            conn,
            event_type="DATABASE_ARCHIVED",
            actor=actor,
            reason=reason,
            trace_id=trace_id,
        )
        await safe_flush(self.db)
        return ConnectionLifecycleResponse(
            database_id=conn.id,
            database_name=conn.name,
            lifecycle_status=conn.lifecycle_status.value,
            message="Connection archived. Intelligence artifacts preserved.",
            preserved_resources=await self._count_related_resources(db_id),
            trace_id=trace_id,
        )

    async def restore_connection(
        self,
        db_id: int,
        *,
        confirmation_text: Optional[str] = None,
        actor: Optional[str] = None,
        reason: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> ConnectionLifecycleResponse:
        conn = await self._get_connection_or_none(db_id)
        if not conn:
            raise ValueError(f"Connection id={db_id} not found")
        if (confirmation_text or "").strip() != conn.name:
            raise ValueError(f"Confirmation text must exactly match connection name '{conn.name}'")
        conn.lifecycle_status = DatabaseLifecycleStatus.active
        conn.status = ConnectionStatus.active
        conn.archived_at = None
        conn.last_error = None
        await self._record_lifecycle_event(
            conn,
            event_type="DATABASE_RESTORED",
            actor=actor,
            reason=reason,
            trace_id=trace_id,
        )
        await safe_flush(self.db)
        return ConnectionLifecycleResponse(
            database_id=conn.id,
            database_name=conn.name,
            lifecycle_status=conn.lifecycle_status.value,
            message="Connection restored.",
            preserved_resources=await self._count_related_resources(db_id),
            trace_id=trace_id,
        )

    async def delete_connection_hard(
        self,
        db_id: int,
        *,
        delete_metadata: bool = True,
        delete_packages: bool = True,
        delete_embeddings: bool = True,
        delete_observability: bool = True,
        confirmation_text: Optional[str] = None,
        actor: Optional[str] = None,
        reason: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> ConnectionLifecycleResponse:
        conn = await self._get_connection_or_none(db_id)
        if not conn:
            raise ValueError(f"Connection id={db_id} not found")
        if (confirmation_text or "").strip() not in {conn.name, f"DELETE {conn.name}"}:
            raise ValueError(f"Confirmation text must exactly match '{conn.name}' or 'DELETE {conn.name}'")

        preserved = await self._count_related_resources(db_id)
        deletion_summary = {
            "delete_metadata": delete_metadata,
            "delete_packages": delete_packages,
            "delete_embeddings": delete_embeddings,
            "delete_observability": delete_observability,
        }
        conn.lifecycle_status = DatabaseLifecycleStatus.deleted
        conn.status = ConnectionStatus.inactive
        conn.deleted_at = datetime.now(timezone.utc)
        conn.deletion_summary = json.dumps(deletion_summary)
        conn.last_error = reason
        await self._record_lifecycle_event(
            conn,
            event_type="DATABASE_DELETED",
            actor=actor,
            reason=reason,
            trace_id=trace_id,
            metadata_json=json.dumps(deletion_summary),
        )

        await self.db.flush()
        await self.db.delete(conn)
        return ConnectionLifecycleResponse(
            database_id=db_id,
            database_name=conn.name,
            lifecycle_status=DatabaseLifecycleStatus.deleted.value,
            message="Connection and requested resources deleted.",
            preserved_resources=preserved,
            deleted_resources=deletion_summary,
            trace_id=trace_id,
        )

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
            lifecycle_status=conn.lifecycle_status.value if hasattr(conn.lifecycle_status, "value") else str(conn.lifecycle_status),
            last_sync_at=conn.last_sync_at,
            created_at=conn.created_at,
            disconnected_at=conn.disconnected_at,
            archived_at=conn.archived_at,
            deleted_at=conn.deleted_at,
            deletion_summary=conn.deletion_summary,
            schema_count=schema_count,
            table_count=table_count,
            last_error=conn.last_error,
        )
