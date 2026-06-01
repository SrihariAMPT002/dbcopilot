"""
MongoDB schema inference service and persistence.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.mongo import MongoConnector
from app.core.security import decrypt_secret
from app.models.metadata import ConnectedDatabase, DatabaseSchema, DatabaseTable, DatabaseType
from app.models.nosql_metadata import (
    NoSQLCollection,
    NoSQLDocumentSample,
    NoSQLRelationship,
    NoSQLSchemaField,
)
from app.utils import safe_flush


class MongoDBService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_mongodb_databases(self) -> list[ConnectedDatabase]:
        result = await self.db.execute(
            select(ConnectedDatabase).where(ConnectedDatabase.db_type == DatabaseType.mongodb)
        )
        return result.scalars().all()

    async def list_collections(self, db_id: int) -> list[NoSQLCollection]:
        await self._ensure_mongodb(db_id)
        result = await self.db.execute(
            select(NoSQLCollection)
            .where(NoSQLCollection.database_id == db_id)
            .order_by(NoSQLCollection.name)
        )
        return result.scalars().all()

    async def get_collection_schema(
        self,
        collection_id: int,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[NoSQLCollection, list[NoSQLSchemaField]]:
        collection = await self.db.get(NoSQLCollection, collection_id)
        if not collection:
            raise ValueError(f"NoSQL collection {collection_id} not found")
        result = await self.db.execute(
            select(NoSQLSchemaField)
            .where(NoSQLSchemaField.collection_id == collection_id)
            .order_by(NoSQLSchemaField.occurrence_percentage.desc(), NoSQLSchemaField.field_path)
            .limit(limit)
            .offset(offset)
        )
        return collection, result.scalars().all()

    async def get_collection_samples(
        self,
        collection_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[NoSQLCollection, list[NoSQLDocumentSample]]:
        collection = await self.db.get(NoSQLCollection, collection_id)
        if not collection:
            raise ValueError(f"NoSQL collection {collection_id} not found")
        result = await self.db.execute(
            select(NoSQLDocumentSample)
            .where(NoSQLDocumentSample.collection_id == collection_id)
            .order_by(NoSQLDocumentSample.sample_index)
            .limit(limit)
            .offset(offset)
        )
        return collection, result.scalars().all()

    async def infer_schema(self, collection_id: int, sample_size: int = 100) -> dict[str, Any]:
        collection = await self.db.get(NoSQLCollection, collection_id)
        if not collection:
            raise ValueError(f"NoSQL collection {collection_id} not found")

        conn = await self._ensure_mongodb(collection.database_id)
        schema_name, collection_name = await self._resolve_schema_collection(conn.id, collection)

        payload = await self._run_inference(conn, schema_name, collection_name, sample_size=sample_size)
        await self._persist_inference(collection, payload)
        return payload

    async def get_relationships(self, collection_id: int) -> tuple[NoSQLCollection, list[NoSQLRelationship]]:
        collection = await self.db.get(NoSQLCollection, collection_id)
        if not collection:
            raise ValueError(f"NoSQL collection {collection_id} not found")
        result = await self.db.execute(
            select(NoSQLRelationship)
            .where(NoSQLRelationship.collection_id == collection_id)
            .order_by(NoSQLRelationship.confidence_score.desc(), NoSQLRelationship.source_field_path)
        )
        return collection, result.scalars().all()

    async def ensure_collection_registry(self, db_id: int) -> list[NoSQLCollection]:
        conn = await self._ensure_mongodb(db_id)
        schema_result = await self.db.execute(
            select(DatabaseSchema).where(DatabaseSchema.connected_db_id == db_id)
        )
        schema = schema_result.scalars().first()
        if not schema:
            return []

        table_result = await self.db.execute(
            select(DatabaseTable).where(DatabaseTable.schema_id == schema.id).order_by(DatabaseTable.name)
        )
        tables = table_result.scalars().all()
        existing = {
            item.table_id: item
            for item in (
                await self.db.execute(
                    select(NoSQLCollection).where(NoSQLCollection.database_id == db_id)
                )
            ).scalars().all()
            if item.table_id is not None
        }

        rows: list[NoSQLCollection] = []
        for table in tables:
            row = existing.get(table.id)
            if row is None:
                row = NoSQLCollection(
                    database_id=db_id,
                    schema_id=schema.id,
                    table_id=table.id,
                    name=table.name,
                    document_count=table.row_count,
                    sampled_documents=0,
                    schema_confidence=0.0,
                )
                self.db.add(row)
            else:
                row.document_count = table.row_count
                row.name = table.name
            rows.append(row)

        await safe_flush(self.db)
        return rows

    async def _ensure_mongodb(self, db_id: int) -> ConnectedDatabase:
        conn = await self.db.get(ConnectedDatabase, db_id)
        if not conn:
            raise ValueError(f"Database {db_id} not found")
        if conn.db_type != DatabaseType.mongodb:
            raise ValueError(f"Database {db_id} is not a MongoDB connection")
        return conn

    async def _resolve_schema_collection(self, db_id: int, collection: NoSQLCollection) -> tuple[str, str]:
        if collection.schema_id:
            schema = await self.db.get(DatabaseSchema, collection.schema_id)
            if schema:
                return schema.name, collection.name
        schema_result = await self.db.execute(
            select(DatabaseSchema).where(DatabaseSchema.connected_db_id == db_id).order_by(DatabaseSchema.name)
        )
        schema = schema_result.scalars().first()
        if not schema:
            raise ValueError(f"No synced MongoDB schema found for database {db_id}")
        return schema.name, collection.name

    async def _run_inference(
        self,
        conn: ConnectedDatabase,
        schema_name: str,
        collection_name: str,
        sample_size: int = 100,
    ) -> dict[str, Any]:
        connector = MongoConnector(
            host=conn.host,
            port=conn.port,
            database=conn.database_name,
            username=conn.username,
            password=decrypt_secret(conn.encrypted_password),
            timeout=30,
            ssl_enabled=bool(getattr(conn, "ssl_enabled", False)),
        )
        async with connector:
            return await connector.infer_collection_schema(
                schema=schema_name,
                collection=collection_name,
                sample_size=sample_size,
            )

    async def _persist_inference(self, collection: NoSQLCollection, payload: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc)
        fields = payload.get("fields", [])
        samples = payload.get("sample_documents", [])
        relationships = payload.get("relationships", [])

        collection.sampled_documents = int(payload.get("sampled_documents", 0))
        collection.schema_confidence = float(payload.get("schema_confidence", 0.0))
        collection.inferred_at = now

        await self.db.execute(
            delete(NoSQLSchemaField).where(NoSQLSchemaField.collection_id == collection.id)
        )
        await self.db.execute(
            delete(NoSQLDocumentSample).where(NoSQLDocumentSample.collection_id == collection.id)
        )
        await self.db.execute(
            delete(NoSQLRelationship).where(NoSQLRelationship.collection_id == collection.id)
        )

        for field in fields:
            self.db.add(
                NoSQLSchemaField(
                    collection_id=collection.id,
                    field_path=field.get("field_path", ""),
                    inferred_data_type=field.get("inferred_data_type", "unknown"),
                    nested_depth=int(field.get("nested_depth", 0)),
                    is_array=bool(field.get("is_array", False)),
                    occurrence_percentage=float(field.get("occurrence_percentage", 0.0)),
                    schema_confidence=float(field.get("schema_confidence", 0.0)),
                    type_distribution=json.dumps(field.get("type_distribution", {})),
                    inferred_at=now,
                )
            )

        for idx, sample in enumerate(samples):
            self.db.add(
                NoSQLDocumentSample(
                    collection_id=collection.id,
                    sample_index=idx,
                    sample_document=json.dumps(sample, default=str),
                    sampled_at=now,
                )
            )

        for rel in relationships:
            self.db.add(
                NoSQLRelationship(
                    collection_id=collection.id,
                    source_field_path=rel.get("source_field_path", ""),
                    target_collection_name=rel.get("target_collection_name", ""),
                    target_field_path=rel.get("target_field_path", "_id"),
                    relationship_type=rel.get("relationship_type", "inferred_ref"),
                    confidence_score=float(rel.get("confidence_score", 0.0)),
                    evidence_count=int(rel.get("evidence_count", 0)),
                    inferred_at=now,
                )
            )
        await safe_flush(self.db)
