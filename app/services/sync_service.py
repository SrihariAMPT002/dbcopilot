"""
SyncService — orchestrates schema discovery and metadata persistence.

Flow:
  1. Load encrypted credentials from the metadata DB
  2. Instantiate the correct connector
  3. Run connector.introspect() → list[SchemaInfo]
  4. Upsert schemas / tables / columns / relationships
  5. Write a SyncLog record
  6. Update ConnectedDatabase.status and last_sync_at
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors import get_connector
from app.connectors.base import ColumnInfo, RelationshipInfo, SchemaInfo, TableInfo
from app.core.security import decrypt_secret
from app.models.metadata import (
    ConnectedDatabase,
    ConnectionStatus,
    DatabaseLifecycleStatus,
    DatabaseColumn,
    DatabaseRelationship,
    DatabaseSchema,
    DatabaseTable,
    SyncLog,
    SyncStatus,
    TableType,
)
from app.models.pipeline_execution import PipelineExecution, StageExecution
from app.schemas.api_schemas import SyncResponse, SyncLogResponse
from app.utils import normalize_column_max_length, safe_flush

logger = logging.getLogger(__name__)


def _log_stage_duration(stage: str, start: float, **fields) -> None:
    elapsed = time.monotonic() - start
    logger.info("%s completed in %.2fs | %s", stage, elapsed, ", ".join(f"{k}={v}" for k, v in fields.items()))


class SyncService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _run_tracked_stage(
        self,
        pipeline_execution: PipelineExecution,
        *,
        stage_name: str,
        execution_order: int,
        db_id: int,
        stage_label: str,
        runner,
    ) -> bool:
        stage_execution = StageExecution(
            pipeline_execution_id=pipeline_execution.id,
            database_id=db_id,
            stage_name=stage_name,
            status="running",
            start_time=datetime.now(timezone.utc),
            execution_order=execution_order,
        )
        self.db.add(stage_execution)
        await safe_flush(self.db)
        success = True
        stage_start = time.monotonic()
        try:
            await runner(db_id)
            stage_execution.status = "completed"
            stage_execution.end_time = datetime.now(timezone.utc)
            stage_execution.duration_seconds = time.monotonic() - stage_start
            _log_stage_duration(stage_label, stage_start, db_id=db_id)
        except Exception as exc:
            success = False
            await self.db.rollback()
            stage_execution.status = "failed"
            stage_execution.end_time = datetime.now(timezone.utc)
            stage_execution.duration_seconds = time.monotonic() - stage_start
            stage_execution.error_message = str(exc)
            logger.exception("Tracked stage failed | db_id=%s stage=%s", db_id, stage_name)
        await safe_flush(self.db)
        return success

    async def _run_governance_stage(self, db_id: int) -> None:
        from app.services.column_semantic_service import ColumnSemanticService

        await ColumnSemanticService(self.db).generate_for_database(db_id, force=False)

    async def _run_semantics_stage(self, db_id: int) -> None:
        from app.services.database_semantic_service import DatabaseSemanticService

        await DatabaseSemanticService(self.db).generate_and_store_semantics(db_id)

    async def _run_relationships_stage(self, db_id: int) -> None:
        from app.schema_engine.relationship_graph import RelationshipGraphEngine

        await RelationshipGraphEngine(self.db).build_relationship_graph(db_id, persist=True)

    async def _run_kpi_stage(self, db_id: int) -> None:
        await KPIIntelligenceService(self.db).generate_for_database(db_id)

    async def _run_prompt_stage(self, db_id: int) -> None:
        from app.services.prompt_studio_service import PromptStudioService

        await PromptStudioService(self.db).generate_artifacts(db_id)

    async def _run_embeddings_stage(self, db_id: int) -> None:
        from app.schema_engine.embeddings import EmbeddingEngine

        await EmbeddingEngine(self.db).generate_database_embeddings(db_id)

    async def _run_readiness_stage(self, db_id: int) -> None:
        from app.services.readiness_service import ReadinessService

        await ReadinessService(self.db).recompute(db_id)

    # ── Public entrypoint ─────────────────────────────────────────────────

    async def sync(self, db_id: int) -> SyncResponse:
        """
        Run a full schema sync for the given connected database.
        Returns a SyncResponse suitable for the API layer.
        """
        # Load the connection record
        conn = await self.db.get(ConnectedDatabase, db_id)
        if not conn:
            return SyncResponse(success=False, message=f"Connection id={db_id} not found")
        lifecycle_status = getattr(conn, "lifecycle_status", DatabaseLifecycleStatus.active)
        if lifecycle_status != DatabaseLifecycleStatus.active:
            return SyncResponse(
                success=False,
                message=f"Connection id={db_id} is {getattr(lifecycle_status, 'value', str(lifecycle_status))}; sync is disabled until it is ACTIVE.",
            )
        conn_db_type = conn.db_type.value

        # Create a pending sync log
        sync_log = SyncLog(
            connected_db_id=db_id,
            status=SyncStatus.running,
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(sync_log)
        await safe_flush(self.db)
        await self.db.refresh(sync_log)

        # Update connection status
        conn.status = ConnectionStatus.active
        await safe_flush(self.db)

        pipeline_execution = PipelineExecution(
            database_id=db_id,
            status="running",
            triggered_by="sync_service",
        )
        self.db.add(pipeline_execution)
        await safe_flush(self.db)
        await self.db.refresh(pipeline_execution)

        start = time.monotonic()
        try:
            metadata_stage = StageExecution(
                pipeline_execution_id=pipeline_execution.id,
                database_id=db_id,
                stage_name="metadata",
                status="running",
                start_time=datetime.now(timezone.utc),
                execution_order=0,
            )
            self.db.add(metadata_stage)
            await safe_flush(self.db)

            stage_start = time.monotonic()
            schemas = await self._run_introspection(conn)
            _log_stage_duration("schema sync / introspection", stage_start, db_id=db_id, schemas=len(schemas))
            stage_start = time.monotonic()
            counts = await self._persist_schemas(db_id, schemas)
            _log_stage_duration(
                "schema sync / persistence",
                stage_start,
                db_id=db_id,
                schemas=counts["schemas"],
                tables=counts["tables"],
                columns=counts["columns"],
                relationships=counts["relationships"],
            )
            await self.db.commit()
            metadata_stage.status = "completed"
            metadata_stage.end_time = datetime.now(timezone.utc)
            metadata_stage.duration_seconds = time.monotonic() - start
            await safe_flush(self.db)

            stage_statuses: list[bool] = []

            stage_statuses.append(
                await self._run_tracked_stage(
                    pipeline_execution,
                    stage_name="governance",
                    execution_order=1,
                    db_id=db_id,
                    stage_label="pii classification",
                    runner=self._run_governance_stage,
                )
            )
            await self.db.commit()

            stage_statuses.append(
                await self._run_tracked_stage(
                    pipeline_execution,
                    stage_name="semantics",
                    execution_order=2,
                    db_id=db_id,
                    stage_label="database semantic generation",
                    runner=self._run_semantics_stage,
                )
            )
            await self.db.commit()

            stage_statuses.append(
                await self._run_tracked_stage(
                    pipeline_execution,
                    stage_name="relationships",
                    execution_order=3,
                    db_id=db_id,
                    stage_label="relationship graph build",
                    runner=self._run_relationships_stage,
                )
            )
            await self.db.commit()

            stage_statuses.append(
                await self._run_tracked_stage(
                    pipeline_execution,
                    stage_name="kpi",
                    execution_order=4,
                    db_id=db_id,
                    stage_label="kpi intelligence generation",
                    runner=self._run_kpi_stage,
                )
            )
            await self.db.commit()

            stage_statuses.append(
                await self._run_tracked_stage(
                    pipeline_execution,
                    stage_name="prompt",
                    execution_order=5,
                    db_id=db_id,
                    stage_label="prompt studio artifact generation",
                    runner=self._run_prompt_stage,
                )
            )
            await self.db.commit()

            stage_statuses.append(
                await self._run_tracked_stage(
                    pipeline_execution,
                    stage_name="embeddings",
                    execution_order=6,
                    db_id=db_id,
                    stage_label="embedding generation",
                    runner=self._run_embeddings_stage,
                )
            )
            await self.db.commit()

            stage_statuses.append(
                await self._run_tracked_stage(
                    pipeline_execution,
                    stage_name="readiness",
                    execution_order=7,
                    db_id=db_id,
                    stage_label="readiness recompute",
                    runner=self._run_readiness_stage,
                )
            )
            await self.db.commit()

            try:
                from app.services.opportunity_service import OpportunityService
                from app.services.data_product_service import DataProductService
                from app.services.warehouse_design_service import WarehouseDesignService
                from app.services.recommendation_service import RecommendationService
                from app.services.predictive_readiness_service import PredictiveReadinessService

                intelligence_start = time.monotonic()
                await OpportunityService(self.db).generate_for_database(db_id)
                await DataProductService(self.db).generate_for_database(db_id)
                await WarehouseDesignService(self.db).generate_for_database(db_id)
                await RecommendationService(self.db).generate_for_database(db_id)
                await PredictiveReadinessService(self.db).generate_for_database(db_id)
                _log_stage_duration("business intelligence generation", intelligence_start, db_id=db_id)
                await self.db.commit()
            except Exception as intelligence_exc:
                logger.exception(
                    "Business intelligence generation failed for db_id=%s: %s",
                    db_id,
                    intelligence_exc,
                )

            if conn_db_type == "mongodb":
                try:
                    from app.services.mongodb_service import MongoDBService

                    mongo_start = time.monotonic()
                    await MongoDBService(self.db).ensure_collection_registry(db_id)
                    _log_stage_duration("mongodb collection registry", mongo_start, db_id=db_id)
                except Exception as nosql_exc:
                    logger.exception(
                        "NoSQL collection registry update failed for db_id=%s: %s",
                        db_id,
                        nosql_exc,
                    )

            elapsed = time.monotonic() - start

            # Finalize sync log
            sync_log.status = SyncStatus.success
            sync_log.completed_at = datetime.now(timezone.utc)
            sync_log.duration_seconds = round(elapsed, 3)
            sync_log.schemas_synced = counts["schemas"]
            sync_log.tables_synced = counts["tables"]
            sync_log.columns_synced = counts["columns"]
            sync_log.relationships_synced = counts["relationships"]
            pipeline_execution.status = "completed" if all(stage_statuses) else "failed"
            pipeline_execution.end_time = datetime.now(timezone.utc)
            pipeline_execution.duration_seconds = elapsed
            pipeline_execution.model_name = None
            pipeline_execution.token_usage_json = None
            pipeline_execution.error_message = None if all(stage_statuses) else "One or more stages failed"

            conn.status = ConnectionStatus.active
            conn.last_sync_at = datetime.now(timezone.utc)
            conn.last_error = None
            await safe_flush(self.db)

            logger.info(
                "Sync complete for db_id=%s: %d schemas, %d tables, %d columns in %.2fs",
                db_id, counts["schemas"], counts["tables"], counts["columns"], elapsed,
            )

            # Convert to DTO inside session before returning
            return SyncResponse(
                success=True,
                message=f"Sync completed in {elapsed:.2f}s",
                sync_log=SyncLogResponse.model_validate(sync_log),
                schemas_discovered=counts["schemas"],
                tables_discovered=counts["tables"],
                columns_discovered=counts["columns"],
            )

        except Exception as exc:
            elapsed = time.monotonic() - start
            error_msg = str(exc)
            logger.error("Sync failed for db_id=%s: %s", db_id, error_msg, exc_info=True)

            await self.db.rollback()

            sync_log.status = SyncStatus.failed
            sync_log.completed_at = datetime.now(timezone.utc)
            sync_log.duration_seconds = round(elapsed, 3)
            sync_log.error_message = error_msg[:1000]

            failure_log = SyncLogResponse(
                id=sync_log.id,
                connected_db_id=sync_log.connected_db_id,
                status=sync_log.status.value,
                started_at=sync_log.started_at,
                completed_at=sync_log.completed_at,
                duration_seconds=sync_log.duration_seconds,
                schemas_synced=sync_log.schemas_synced,
                tables_synced=sync_log.tables_synced,
                columns_synced=sync_log.columns_synced,
                relationships_synced=sync_log.relationships_synced,
                error_message=sync_log.error_message,
            )

            try:
                await safe_flush(self.db)
            except Exception:
                logger.exception(
                    "Failed to flush sync failure state for db_id=%s; session rolled back",
                    db_id,
                )

            conn = await self.db.get(ConnectedDatabase, db_id)
            if conn:
                conn.status = ConnectionStatus.error
                conn.last_error = error_msg[:500]
                try:
                    await safe_flush(self.db)
                except Exception:
                    logger.exception(
                        "Failed to persist sync failure state for db_id=%s after rollback",
                        db_id,
                    )

            return SyncResponse(
                success=False,
                message=f"Sync failed: {error_msg}",
                sync_log=failure_log,
            )

    # ── Introspection ─────────────────────────────────────────────────────

    async def _run_introspection(self, conn: ConnectedDatabase) -> List[SchemaInfo]:
        password = decrypt_secret(conn.encrypted_password)
        connector = get_connector(
            db_type=conn.db_type,
            host=conn.host,
            port=conn.port,
            database=conn.database_name,
            username=conn.username,
            password=password,
            ssl_enabled=bool(getattr(conn, "ssl_enabled", False)),
        )
        async with connector:
            schemas = await connector.introspect()
        return schemas

    # ── Persistence ───────────────────────────────────────────────────────

    async def _persist_schemas(
        self, db_id: int, schemas: List[SchemaInfo]
    ) -> Dict[str, int]:
        """
        Upsert all discovered schemas/tables/columns/relationships.
        Deletes schemas that no longer exist on the source.
        Returns counts of persisted objects.
        """
        counts = {"schemas": 0, "tables": 0, "columns": 0, "relationships": 0}
        discovered_schema_names = {s.name for s in schemas}

        # --- Remove stale schemas ---
        existing_schemas_result = await self.db.execute(
            select(DatabaseSchema).where(DatabaseSchema.connected_db_id == db_id)
        )
        existing_schemas = {s.name: s for s in existing_schemas_result.scalars().all()}
        for name, schema_obj in existing_schemas.items():
            if name not in discovered_schema_names:
                await self.db.delete(schema_obj)

        # --- Upsert schemas ---
        schema_map: Dict[str, DatabaseSchema] = {}
        for schema_info in schemas:
            schema_obj = existing_schemas.get(schema_info.name)
            if schema_obj is None:
                schema_obj = DatabaseSchema(
                    connected_db_id=db_id,
                    name=schema_info.name,
                )
                self.db.add(schema_obj)
                await safe_flush(self.db)
                await self.db.refresh(schema_obj)
            schema_map[schema_info.name] = schema_obj
            counts["schemas"] += 1

            counts_t = await self._persist_tables(schema_obj.id, schema_info.tables)
            counts["tables"] += counts_t["tables"]
            counts["columns"] += counts_t["columns"]
            counts["relationships"] += counts_t["relationships"]

        await safe_flush(self.db)
        return counts

    async def _persist_tables(
        self, schema_id: int, tables: List[TableInfo]
    ) -> Dict[str, int]:
        counts = {"tables": 0, "columns": 0, "relationships": 0}
        discovered_names = {t.name for t in tables}

        # Load existing tables for this schema
        existing_result = await self.db.execute(
            select(DatabaseTable).where(DatabaseTable.schema_id == schema_id)
        )
        existing_tables = {t.name: t for t in existing_result.scalars().all()}

        # Remove stale
        for name, tbl in existing_tables.items():
            if name not in discovered_names:
                await self.db.delete(tbl)

        # Upsert
        for tbl_info in tables:
            tbl_obj = existing_tables.get(tbl_info.name)
            table_type = _to_table_type(tbl_info.table_type)

            if tbl_obj is None:
                tbl_obj = DatabaseTable(
                    schema_id=schema_id,
                    name=tbl_info.name,
                    table_type=table_type,
                    row_count=tbl_info.row_count,
                )
                self.db.add(tbl_obj)
            else:
                tbl_obj.table_type = table_type
                tbl_obj.row_count = tbl_info.row_count

            await safe_flush(self.db)
            await self.db.refresh(tbl_obj)
            counts["tables"] += 1

            # Columns
            col_count = await self._persist_columns(tbl_obj.id, tbl_info.columns)
            counts["columns"] += col_count

            # Relationships
            rel_count = await self._persist_relationships(tbl_obj.id, tbl_info.relationships)
            counts["relationships"] += rel_count

        return counts

    async def _persist_columns(
        self, table_id: int, columns: List[ColumnInfo]
    ) -> int:
        # Delete all existing columns for this table and re-insert
        # (simpler than diffing individual columns)
        await self.db.execute(
            delete(DatabaseColumn).where(DatabaseColumn.table_id == table_id)
        )
        for col in columns:
            self.db.add(
                DatabaseColumn(
                    table_id=table_id,
                    name=col.name,
                    data_type=col.data_type,
                    ordinal_position=col.ordinal_position,
                    is_nullable=col.is_nullable,
                    is_primary_key=col.is_primary_key,
                    is_foreign_key=col.is_foreign_key,
                    is_unique=col.is_unique,
                    is_indexed=col.is_indexed,
                    default_value=col.default_value,
                    max_length=normalize_column_max_length(col.data_type, col.max_length),
                )
            )
        await safe_flush(self.db)
        return len(columns)

    async def _persist_relationships(
        self, table_id: int, relationships: List[RelationshipInfo]
    ) -> int:
        await self.db.execute(
            delete(DatabaseRelationship).where(DatabaseRelationship.table_id == table_id)
        )
        for rel in relationships:
            self.db.add(
                DatabaseRelationship(
                    table_id=table_id,
                    column_name=rel.column_name,
                    referenced_schema=rel.referenced_schema,
                    referenced_table_name=rel.referenced_table,
                    referenced_column_name=rel.referenced_column,
                    constraint_name=rel.constraint_name,
                )
            )
        await safe_flush(self.db)
        return len(relationships)


def _to_table_type(raw: str) -> TableType:
    mapping = {
        "table": TableType.table,
        "view": TableType.view,
        "materialized_view": TableType.materialized_view,
        "foreign_table": TableType.foreign_table,
    }
    return mapping.get(raw.lower(), TableType.table)
