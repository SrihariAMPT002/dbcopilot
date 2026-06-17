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

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, delete, update
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
from app.services.kpi_intelligence_service import KPIIntelligenceService
from app.services.cache_service import cache_service
from app.core.structured_logging import error_message, stage_message, sync_message
from app.utils import normalize_column_max_length, safe_flush

logger = logging.getLogger(__name__)


def _log_stage_duration(stage: str, start: float, **fields) -> None:
    elapsed = time.monotonic() - start
    logger.info(stage_message(f"{stage} completed in {elapsed:.2f}s", **fields))


class SyncService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {str(key): SyncService._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [SyncService._json_safe(item) for item in value]
        if hasattr(value, "__dict__"):
            return SyncService._json_safe({k: v for k, v in vars(value).items() if not k.startswith("_")})
        return str(value)

    async def _run_tracked_stage(
        self,
        pipeline_execution_id: int,
        *,
        stage_name: str,
        execution_order: int,
        db_id: int,
        stage_label: str,
        runner,
    ) -> tuple[bool, Any]:
        stage_execution = StageExecution(
            pipeline_execution_id=pipeline_execution_id,
            database_id=db_id,
            stage_name=stage_name,
            status="running",
            start_time=datetime.now(timezone.utc),
            execution_order=execution_order,
        )
        self.db.add(stage_execution)
        await safe_flush(self.db)
        stage_execution_id = stage_execution.id
        success = True
        stage_output: Any = None
        stage_start = time.monotonic()
        try:
            stage_output = await runner(db_id)
            stage_execution.status = "completed"
            stage_execution.end_time = datetime.now(timezone.utc)
            stage_execution.duration_seconds = time.monotonic() - stage_start
            if isinstance(stage_output, dict):
                stage_execution.context_source = stage_output.get("context_source")
                stage_execution.used_context = stage_output.get("used_context")
                stage_execution.fallback_reason = stage_output.get("fallback_reason")
            _log_stage_duration(stage_label, stage_start, db_id=db_id)
        except Exception as exc:
            success = False
            await self.db.rollback()
            failed_stage = await self.db.get(StageExecution, stage_execution_id)
            if failed_stage is not None:
                failed_stage.status = "failed"
                failed_stage.end_time = datetime.now(timezone.utc)
                failed_stage.duration_seconds = time.monotonic() - stage_start
                failed_stage.error_message = str(exc)
            logger.exception(error_message("tracked stage failed", db_id=db_id, stage=stage_name))
        await safe_flush(self.db)
        return success, stage_output

    async def _block_remaining_stages(
        self,
        *,
        pipeline_execution_id: int,
        db_id: int,
        blocked_by_stage: str,
        remaining_stages: list[tuple[int, str]],
        reason: str,
    ) -> None:
        for execution_order, stage_name in remaining_stages:
            stage_execution = StageExecution(
                pipeline_execution_id=pipeline_execution_id,
                database_id=db_id,
                stage_name=stage_name,
                status="blocked",
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
                execution_order=execution_order,
                blocked_by_stage=blocked_by_stage,
                error_message=reason,
            )
            self.db.add(stage_execution)
        await safe_flush(self.db)

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

        async with cache_service.lock(f"sync:{db_id}", ttl_seconds=1800) as acquired:
            if not acquired:
                return SyncResponse(success=False, message="Sync already running.")

            sync_log = SyncLog(
                connected_db_id=db_id,
                status=SyncStatus.running,
                started_at=datetime.now(timezone.utc),
            )
            self.db.add(sync_log)
            await safe_flush(self.db)
            await self.db.refresh(sync_log)
            sync_log_id = sync_log.id
            sync_log_started_at = sync_log.started_at
            sync_log_connected_db_id = db_id

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
            pipeline_execution_id = pipeline_execution.id

            pipeline_context: dict[str, Any] = {"database_id": db_id, "stages": {}}
            pipeline_context_source: str | None = None
            pipeline_used_context: bool | None = None
            pipeline_fallback_reason: str | None = None

            def _stage_provenance(value: Any) -> tuple[Any, Any, Any]:
                if isinstance(value, dict):
                    return value.get("context_source"), value.get("used_context"), value.get("fallback_reason")
                return (
                    getattr(value, "context_source", None),
                    getattr(value, "used_context", None),
                    getattr(value, "fallback_reason", None),
                )

            start = time.monotonic()
            counts = {"schemas": 0, "tables": 0, "columns": 0, "relationships": 0}
            try:
                metadata_stage = StageExecution(
                    pipeline_execution_id=pipeline_execution_id,
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
                metadata_stage.status = "completed"
                metadata_stage.end_time = datetime.now(timezone.utc)
                metadata_stage.duration_seconds = time.monotonic() - start
                await safe_flush(self.db)
                await self.db.commit()

                stage_successes: list[bool] = []
                failed_stage_name: str | None = None
                stages = [
                    (1, "governance", "pii classification", self._run_governance_stage),
                    (2, "semantics", "database semantic generation", self._run_semantics_stage),
                    (3, "relationships", "relationship graph build", self._run_relationships_stage),
                    (4, "kpi", "kpi intelligence generation", self._run_kpi_stage),
                    (5, "prompt", "prompt studio artifact generation", self._run_prompt_stage),
                    (6, "embeddings", "embedding generation", self._run_embeddings_stage),
                    (7, "readiness", "readiness recompute", self._run_readiness_stage),
                ]
                for index, (execution_order, stage_name, stage_label, runner) in enumerate(stages):
                    success, stage_output = await self._run_tracked_stage(
                        pipeline_execution_id,
                        stage_name=stage_name,
                        execution_order=execution_order,
                        db_id=db_id,
                        stage_label=stage_label,
                        runner=runner,
                    )
                    stage_successes.append(success)
                    pipeline_context["stages"][stage_name] = self._json_safe(stage_output)
                    context_source, used_context, fallback_reason = _stage_provenance(stage_output)
                    if pipeline_context_source is None:
                        pipeline_context_source = context_source
                        pipeline_used_context = used_context
                        pipeline_fallback_reason = fallback_reason
                    await self.db.commit()
                    if not success:
                        failed_stage_name = stage_name
                        remaining = [(order, name) for order, name, _, _ in stages[index + 1 :]]
                        if remaining:
                            await self._block_remaining_stages(
                                pipeline_execution_id=pipeline_execution_id,
                                db_id=db_id,
                                blocked_by_stage=stage_name,
                                remaining_stages=remaining,
                                reason=f"Blocked by failed stage: {stage_name}",
                            )
                        break

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
                    logger.exception(error_message("business intelligence generation failed", db_id=db_id, reason=intelligence_exc))

                if conn_db_type == "mongodb":
                    try:
                        from app.services.mongodb_service import MongoDBService

                        mongo_start = time.monotonic()
                        await MongoDBService(self.db).ensure_collection_registry(db_id)
                        _log_stage_duration("mongodb collection registry", mongo_start, db_id=db_id)
                    except Exception as nosql_exc:
                        logger.exception(error_message("nosql collection registry update failed", db_id=db_id, reason=nosql_exc))

                elapsed = time.monotonic() - start
                sync_log.status = SyncStatus.success
                sync_log.completed_at = datetime.now(timezone.utc)
                sync_log.duration_seconds = round(elapsed, 3)
                sync_log.schemas_synced = counts["schemas"]
                sync_log.tables_synced = counts["tables"]
                sync_log.columns_synced = counts["columns"]
                sync_log.relationships_synced = counts["relationships"]
                pipeline_execution.status = "completed" if all(stage_successes) else "failed"
                pipeline_execution.end_time = datetime.now(timezone.utc)
                pipeline_execution.duration_seconds = elapsed
                pipeline_execution.context_source = pipeline_context_source
                pipeline_execution.used_context = pipeline_used_context
                pipeline_execution.fallback_reason = pipeline_fallback_reason
                pipeline_execution.model_name = None
                pipeline_execution.token_usage_json = None
                pipeline_execution.pipeline_context_json = json.dumps(pipeline_context, default=str)
                pipeline_execution.error_message = None if all(stage_successes) else "One or more stages failed"
                pipeline_execution.blocked_by_stage = None if all(stage_successes) else failed_stage_name
                conn.status = ConnectionStatus.active
                conn.last_sync_at = datetime.now(timezone.utc)
                conn.last_error = None
                await safe_flush(self.db)
                await cache_service.delete(f"readiness:{db_id}")
                await cache_service.invalidate_pattern(f"relationships:{db_id}:*")
                await cache_service.invalidate_pattern(f"kpi:{db_id}:*")
                await cache_service.invalidate_pattern(f"embeddings:{db_id}:*")
                await cache_service.invalidate_pattern(f"context:{db_id}:*")
                await cache_service.invalidate_pattern(f"pipeline:{db_id}:*")
                logger.info(
                    sync_message(
                        f"complete in {elapsed:.2f}s",
                        db_id=db_id,
                        schemas=counts["schemas"],
                        tables=counts["tables"],
                        columns=counts["columns"],
                    )
                )
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
                logger.error(error_message("sync failed", db_id=db_id, reason=error_msg), exc_info=True)
                await self.db.rollback()
                failure_log = SyncLogResponse(
                    id=sync_log_id,
                    connected_db_id=sync_log_connected_db_id,
                    status=SyncStatus.failed.value,
                    started_at=sync_log_started_at,
                    completed_at=datetime.now(timezone.utc),
                    duration_seconds=round(elapsed, 3),
                    schemas_synced=counts["schemas"],
                    tables_synced=counts["tables"],
                    columns_synced=counts["columns"],
                    relationships_synced=counts["relationships"],
                    error_message=error_msg[:1000],
                )
                try:
                    await self.db.execute(
                        update(SyncLog)
                        .where(SyncLog.id == sync_log_id)
                        .values(
                            status=SyncStatus.failed,
                            completed_at=failure_log.completed_at,
                            duration_seconds=failure_log.duration_seconds,
                            schemas_synced=failure_log.schemas_synced,
                            tables_synced=failure_log.tables_synced,
                            columns_synced=failure_log.columns_synced,
                            relationships_synced=failure_log.relationships_synced,
                            error_message=failure_log.error_message,
                        )
                    )
                    await safe_flush(self.db)
                except Exception:
                    logger.exception(error_message("failed to flush sync failure state", db_id=db_id))
                try:
                    await self.db.execute(
                        update(ConnectedDatabase)
                        .where(ConnectedDatabase.id == db_id)
                        .values(status=ConnectionStatus.error, last_error=error_msg[:500])
                    )
                    await safe_flush(self.db)
                except Exception:
                    logger.exception(error_message("failed to persist sync failure state after rollback", db_id=db_id))
                return SyncResponse(success=False, message=f"Sync failed: {error_msg}", sync_log=failure_log)

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
