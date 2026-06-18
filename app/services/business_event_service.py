"""Business event detection from metadata."""

from __future__ import annotations

import json
import hashlib
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.prompts import get_prompt_registry
from app.core.config import settings
from app.models.business_event import BusinessEvent
from app.models.metadata import DatabaseRelationship, DatabaseSchema, DatabaseTable
from app.services.ai_observability_service import AIObservabilityService


class BusinessEventService:
    EVENT_HINTS = ("created", "updated", "submitted", "completed", "approved", "scheduled", "registered", "opened", "closed", "processed")

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.registry = get_prompt_registry()

    async def detect_for_database(self, database_id: int) -> list[dict[str, Any]]:
        tables = await self._fetch_tables(database_id)
        relationships = await self._fetch_relationships(database_id)
        candidates: list[dict[str, Any]] = []

        for table in tables:
            event = self._infer_event(table, relationships)
            if event:
                candidates.append(event)

        candidates = await self._enrich_with_ai(
            database_id=database_id,
            tables=tables,
            relationships=relationships,
            events=candidates,
        )
        await self._persist(database_id, candidates)
        return candidates

    async def get_events(self, database_id: int) -> dict[str, Any]:
        result = await self.db.execute(
            select(BusinessEvent).where(BusinessEvent.database_id == database_id).order_by(BusinessEvent.confidence_score.desc())
        )
        rows = result.scalars().all()
        return {
            "database_id": database_id,
            "events": [
                {
                    "id": row.id,
                    "event_name": row.event_name,
                    "event_type": row.event_type,
                    "source_tables": json.loads(row.source_tables or "[]"),
                    "confidence_score": row.confidence_score,
                    "trace_id": row.trace_id,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ],
        }

    async def get_health(self, database_id: int) -> dict[str, Any]:
        result = await self.db.execute(
            select(BusinessEvent).where(BusinessEvent.database_id == database_id).order_by(BusinessEvent.created_at.desc())
        )
        rows = result.scalars().all()
        latest = rows[0] if rows else None
        return {
            "database_id": database_id,
            "event_rows": len(rows),
            "latest_trace_id": getattr(latest, "trace_id", None),
            "state": "empty" if not rows else "healthy",
        }

    def _infer_event(self, table: DatabaseTable, relationships: list[DatabaseRelationship]) -> dict[str, Any] | None:
        table_name = table.name or ""
        lowered = table_name.lower()
        table_tokens = [token for token in lowered.replace("-", "_").split("_") if token]
        has_temporal = any(token in (col.name or "").lower() for token in ("created", "updated", "date", "time", "timestamp"))
        has_status = any(token in (col.name or "").lower() for token in ("status", "state", "stage", "event"))
        has_identifier = any(
            (col.name or "").lower().endswith("_id") or (col.name or "").lower() == "id"
            for col in (table.columns or [])
        )

        signal = sum(1 for token in self.EVENT_HINTS if token in lowered)
        score = 0.35 + 0.1 * signal
        if has_temporal:
            score += 0.2
        if has_status:
            score += 0.1
        if relationships:
            score += 0.05
        if score < 0.45:
            return None

        event_name = self._humanize_event_name(table_tokens, table.name)
        source_tables = self._source_tables(table, relationships)
        event_type = "lifecycle" if has_temporal else "transaction"
        return {
            "event_name": event_name,
            "event_type": event_type,
            "source_tables": source_tables,
            "confidence_score": round(min(0.95, score), 2),
        }

    async def _enrich_with_ai(
        self,
        *,
        database_id: int,
        tables: list[DatabaseTable],
        relationships: list[DatabaseRelationship],
        events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        prompt_payload = {
            "database_context": {
                "database_id": database_id,
                "table_count": len(tables),
                "relationship_count": len(relationships),
            },
            "governance_package": [],
            "semantic_package": {},
            "relationship_package": {"relationships": [self._relationship_row(rel) for rel in relationships[:25]]},
            "graph_features": {
                "table_names": [table.name for table in tables[:25]],
            },
            "events": events,
        }
        try:
            rendered = self.registry.render_prompt("business_event_detection", prompt_payload, category="events")
            result = await AIObservabilityService().generate(
                operation="chat",
                module="business_events",
                artifact_type="business_event_detection",
                prompt_id=rendered.metadata.id,
                prompt_version=rendered.metadata.version,
                model_name=settings.azure_openai_deployment,
                messages=[
                    {"role": "system", "content": rendered.system_message or "You are a business event inference engine."},
                    {"role": "user", "content": rendered.user_prompt},
                ],
                request_kwargs={"response_format": {"type": "json_object"}},
                completeness_score=0.0,
                coverage_score=0.0,
                confidence_score=0.0,
                execution_status="success",
                fallback_used=False,
                retry_count=0,
                extra_metadata={"feature": "business_events"},
            )
            payload = json.loads(result.content or "{}")
            detected = payload.get("events")
            if isinstance(detected, list) and detected:
                return detected
        except Exception:
            pass
        return events

    async def _persist(self, database_id: int, events: list[dict[str, Any]]) -> None:
        result = await self.db.execute(
            select(BusinessEvent).where(BusinessEvent.database_id == database_id).order_by(BusinessEvent.created_at.desc())
        )
        existing_rows = result.scalars().all()
        existing_signatures = {
            self._event_signature(
                row.event_name,
                row.event_type,
                json.loads(row.source_tables or "[]"),
            )
            for row in existing_rows
        }
        for event in events:
            signature = self._event_signature(
                event["event_name"],
                event.get("event_type"),
                event.get("source_tables", []),
            )
            if signature in existing_signatures:
                continue
            self.db.add(
                BusinessEvent(
                    database_id=database_id,
                    event_name=event["event_name"],
                    event_type=event.get("event_type"),
                    source_tables=json.dumps(event.get("source_tables", []), default=str),
                    confidence_score=float(event.get("confidence_score", 0.0)),
                    trace_id=event.get("trace_id"),
                )
            )
        await self.db.flush()

    async def _fetch_tables(self, database_id: int) -> list[DatabaseTable]:
        result = await self.db.execute(
            select(DatabaseTable)
            .join(DatabaseSchema)
            .options(
                selectinload(DatabaseTable.schema),
                selectinload(DatabaseTable.columns),
                selectinload(DatabaseTable.relationships_from),
            )
            .where(DatabaseSchema.connected_db_id == database_id)
        )
        return list(result.scalars().all())

    async def _fetch_relationships(self, database_id: int) -> list[DatabaseRelationship]:
        result = await self.db.execute(
            select(DatabaseRelationship)
            .join(DatabaseTable, DatabaseRelationship.table_id == DatabaseTable.id)
            .join(DatabaseSchema, DatabaseTable.schema_id == DatabaseSchema.id)
            .where(DatabaseSchema.connected_db_id == database_id)
        )
        return list(result.scalars().all())

    def _source_tables(self, table: DatabaseTable, relationships: list[DatabaseRelationship]) -> list[str]:
        source_tables = {table.name}
        for rel in relationships:
            if rel.table_id == table.id:
                source_tables.add(table.name)
                if getattr(rel, "referenced_table_name", None):
                    source_tables.add(rel.referenced_table_name)
                if getattr(rel, "referenced_table_id", None):
                    source_tables.add(str(rel.referenced_table_id))
        return sorted(name for name in source_tables if name)[:5]

    @staticmethod
    def _event_signature(event_name: str, event_type: str | None, source_tables: list[str]) -> str:
        payload = json.dumps(
            {
                "event_name": event_name,
                "event_type": event_type or "",
                "source_tables": sorted(str(item) for item in source_tables if item),
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _relationship_row(rel: DatabaseRelationship) -> dict[str, Any]:
        return {
            "table_id": rel.table_id,
            "column_name": rel.column_name,
            "referenced_table_id": rel.referenced_table_id,
            "referenced_column_name": rel.referenced_column_name,
            "constraint_name": getattr(rel, "constraint_name", None),
        }

    @staticmethod
    def _humanize_event_name(tokens: list[str], fallback: str) -> str:
        if not tokens:
            tokens = [fallback]
        words = [word for word in tokens if word not in {"tbl", "table", "data"}]
        if not words:
            words = [fallback]
        return " ".join(word.capitalize() for word in words[:4]) + " Event"
