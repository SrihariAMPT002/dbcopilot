"""
Schema embeddings engine.

Builds vector representations for schema tables, relationships, and prompt
contexts using Azure OpenAI embeddings, then stores them in Qdrant and the
internal metadata DB.
"""

from __future__ import annotations

import asyncio
import json
import logging
import inspect
import time
import uuid
from dataclasses import dataclass, field
from functools import wraps
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.column_semantic import ColumnSemantic
from app.models.metadata import (
    ConnectedDatabase,
    DatabaseRelationship,
    DatabaseSchema,
    DatabaseTable,
    GovernancePackage,
    EmbeddingStatus,
    SchemaEmbedding,
    SchemaSemantic,
    SemanticPackage,
    RelationshipPackage,
)
from app.services.ai_observability_service import AIObservabilityService
from app.utils import safe_flush, truncate
from app.config.package_registry import package_is_enabled

logger = logging.getLogger(__name__)


def _log_stage_duration(stage: str, start: float, **fields) -> None:
    elapsed = time.monotonic() - start
    logger.info("%s completed in %.2fs | %s", stage, elapsed, ", ".join(f"{k}={v}" for k, v in fields.items()))

COLLECTION_SCHEMA_TABLES = "schema_tables"
COLLECTION_SCHEMA_RELATIONSHIPS = "schema_relationships"
COLLECTION_SCHEMA_PROMPTS = "schema_prompts"

EMBEDDING_COLLECTIONS = (
    COLLECTION_SCHEMA_TABLES,
    COLLECTION_SCHEMA_RELATIONSHIPS,
    COLLECTION_SCHEMA_PROMPTS,
)

_qdrant_client = None

try:  # Optional dependency.
    from langsmith import traceable
except Exception:  # pragma: no cover - optional dependency.
    traceable = None

try:  # Optional dependency.
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels
except Exception:  # pragma: no cover - optional dependency.
    QdrantClient = None
    qmodels = None


@dataclass
class EmbeddingArtifact:
    collection_name: str
    point_id: str
    text: str
    payload: Dict[str, Any]
    vector: List[float] = field(default_factory=list)


@dataclass
class EmbeddingBatchResult:
    database_id: int
    database_name: str
    embedding_model: str
    tables_indexed: int = 0
    vectors_indexed: int = 0
    token_usage: Dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0
    success: bool = True
    message: str = ""


def _traceable(name: str, run_type: str = "chain"):
    """Return a trace decorator when LangSmith tracing is enabled."""

    def decorator(fn):
        if not settings.langsmith_tracing or traceable is None:
            if inspect.iscoroutinefunction(fn):
                @wraps(fn)
                async def passthrough(*args, **kwargs):
                    return await fn(*args, **kwargs)
            else:
                @wraps(fn)
                def passthrough(*args, **kwargs):
                    return fn(*args, **kwargs)
            return passthrough
        return traceable(name=name, run_type=run_type)(fn)

    return decorator


def _resolve_qdrant_url() -> str:
    if settings.qdrant_url:
        return settings.qdrant_url
    if settings.qdrant_host:
        return f"http://{settings.qdrant_host}:{settings.qdrant_port}"
    return f"http://qdrant:{settings.qdrant_port}"


def get_qdrant_client():
    """Return a cached Qdrant client."""

    global _qdrant_client
    if _qdrant_client is not None:
        return _qdrant_client

    if QdrantClient is None:
        raise ImportError("qdrant-client is required for vector indexing and retrieval")

    _qdrant_client = QdrantClient(url=_resolve_qdrant_url(), timeout=10)
    return _qdrant_client


def _stable_point_id(collection_name: str, database_id: int, table_id: int) -> str:
    key = f"{collection_name}:{database_id}:{table_id}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def _count_token_usage(response: Any) -> Dict[str, int]:
    usage = getattr(response, "usage", None)
    if not usage:
        return {}
    return {
        "input_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
    }


class EmbeddingEngine:
    """Generate schema embeddings and persist them to Qdrant."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _embed_texts(
        self,
        texts: Sequence[str],
        *,
        database_id: int | None = None,
        database_name: str | None = None,
        table_name: str | None = None,
        artifact_type: str = "schema_embedding",
    ) -> tuple[List[List[float]], Dict[str, int]]:
        if not texts:
            return [], {}

        dimensions = settings.azure_openai_embedding_dimensions
        observability = AIObservabilityService()
        ai_start = time.monotonic()
        result = await observability.generate(
            operation="embeddings",
            module="semantic_intelligence",
            artifact_type=artifact_type,
            database_id=database_id,
            database_name=database_name,
            prompt_id="embedding",
            prompt_version="1",
            model_name=settings.azure_openai_embedding_deployment,
            input_texts=list(texts),
            request_kwargs={"dimensions": dimensions} if dimensions else {},
            completeness_score=1.0 if texts else 0.0,
            coverage_score=min(1.0, len(texts) / 3.0),
            confidence_score=0.0,
            extra_metadata={
                "table_name": table_name,
                "text_count": len(texts),
            },
        )
        vectors = result.embeddings or []
        usage = result.token_usage
        _log_stage_duration(
            "embedding generation / azure openai",
            ai_start,
            database_id=database_id,
            database_name=database_name,
            table_name=table_name,
            artifact_type=artifact_type,
            text_count=len(texts),
        )
        logger.info(
            "Embedded %d text(s) | model=%s dim=%d in %.2fms",
            len(texts),
            settings.azure_openai_embedding_deployment,
            dimensions,
            result.latency_ms,
        )
        if usage:
            logger.info("Token usage: %s", usage)
        return vectors, usage

    async def _embed_text(self, text: str) -> tuple[List[float], Dict[str, int]]:
        vectors, usage = await self._embed_texts([text])
        return vectors[0], usage

    def _ensure_collections(self, vector_size: Optional[int] = None) -> None:
        client = get_qdrant_client()
        if qmodels is None:
            raise ImportError("qdrant-client is required for vector indexing and retrieval")

        # Always prefer the configured dimension; fall back to the measured one only
        # if config is 0 / None (shouldn't happen, but safe)
        size = settings.azure_openai_embedding_dimensions or vector_size
        if not size:
            raise ValueError(
                "Cannot create Qdrant collections: embedding dimensions not configured. "
                "Set AZURE_OPENAI_EMBEDDING_DIMENSIONS in your .env."
            )

        for collection_name in EMBEDDING_COLLECTIONS:
            try:
                existing = client.get_collection(collection_name)
                existing_size = existing.config.params.vectors.size
                if existing_size != size:
                    logger.warning(
                        "Collection %s has vector size %d but config says %d. "
                        "Delete the collection and re-index if you changed dimensions.",
                        collection_name, existing_size, size,
                    )
            except Exception:
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=qmodels.VectorParams(
                        size=size,
                        distance=qmodels.Distance.COSINE,
                    ),
                )
                logger.info(
                    "Created Qdrant collection %s (size=%d, distance=COSINE)",
                    collection_name,
                    size,
                )

    async def _fetch_database(self, database_id: int) -> ConnectedDatabase:
        result = await self.db.execute(
            select(ConnectedDatabase).where(ConnectedDatabase.id == database_id)
        )
        database = result.scalars().first()
        if not database:
            raise ValueError(f"Database {database_id} not found")
        return database

    async def _fetch_tables(self, database_id: int) -> List[DatabaseTable]:
        result = await self.db.execute(
            select(DatabaseTable)
            .join(DatabaseSchema)
            .options(
                selectinload(DatabaseTable.schema).selectinload(DatabaseSchema.connected_database),
                selectinload(DatabaseTable.columns),
                selectinload(DatabaseTable.relationships_from),
            )
            .where(DatabaseSchema.connected_db_id == database_id)
            .order_by(DatabaseSchema.name, DatabaseTable.name)
        )
        return result.scalars().unique().all()

    async def _fetch_semantic_summary(self, table_id: int) -> Optional[SchemaSemantic]:
        result = await self.db.execute(
            select(SchemaSemantic).where(SchemaSemantic.table_id == table_id)
        )
        return result.scalars().first()

    async def _fetch_pii_map(self, database_id: int) -> dict[int, ColumnSemantic]:
        result = await self.db.execute(
            select(ColumnSemantic).where(ColumnSemantic.database_id == database_id)
        )
        return {row.column_id: row for row in result.scalars().all()}

    async def _fetch_governance_packages(self, database_id: int) -> dict[int, GovernancePackage]:
        result = await self.db.execute(
            select(GovernancePackage).where(GovernancePackage.database_id == database_id)
        )
        return {row.table_id: row for row in result.scalars().all()}

    async def _fetch_semantic_package(self, database_id: int) -> SemanticPackage | None:
        result = await self.db.execute(
            select(SemanticPackage).where(SemanticPackage.database_id == database_id)
        )
        return result.scalars().first()

    async def _fetch_relationship_packages(self, database_id: int) -> list[RelationshipPackage]:
        result = await self.db.execute(
            select(RelationshipPackage).where(RelationshipPackage.database_id == database_id)
        )
        return list(result.scalars().all())

    @staticmethod
    def _should_mask_column(
        column_id: int,
        pii_map: dict[int, ColumnSemantic] | None,
    ) -> bool:
        if not settings.pii_embedding_protection_enabled or not pii_map:
            return False
        semantic_row = pii_map.get(column_id)
        if not semantic_row:
            return False
        if semantic_row.is_pii:
            return True
        return bool(semantic_row.risk_level and semantic_row.risk_level.lower() in {"high", "critical"})

    def _build_table_text(
        self,
        table: DatabaseTable,
        semantic: Optional[SchemaSemantic],
        pii_map: dict[int, ColumnSemantic] | None = None,
    ) -> str:
        lines = [
            f"Database table: {table.schema.connected_database.name if table.schema and table.schema.connected_database else 'unknown'}",
            f"Schema: {table.schema.name}",
            f"Table: {table.name}",
            f"Type: {table.table_type.value}",
        ]
        if table.description:
            lines.append(f"Description: {table.description}")
        if table.row_count is not None:
            lines.append(f"Approx rows: {table.row_count}")
        if semantic and semantic.semantic_summary:
            lines.append(f"Business summary: {semantic.semantic_summary}")

        lines.append("Columns:")
        for column in sorted(table.columns, key=lambda item: item.ordinal_position or 0):
            if self._should_mask_column(column.id, pii_map):
                semantic_row = pii_map.get(column.id) if pii_map else None
                pii_label = semantic_row.pii_type if semantic_row and semantic_row.pii_type else "PII"
                risk = semantic_row.risk_level if semantic_row else "unknown"
                lines.append(f" - [PII PROTECTED] ({pii_label}, risk={risk})")
                continue
            flags = []
            if column.is_primary_key:
                flags.append("PK")
            if column.is_foreign_key:
                flags.append("FK")
            if column.is_unique:
                flags.append("UQ")
            if not column.is_nullable:
                flags.append("NN")
            flag_text = f" [{', '.join(flags)}]" if flags else ""
            description = f" - {column.name}: {column.data_type}{flag_text}"
            if column.description:
                description += f" | {column.description}"
            lines.append(description)

        if semantic:
            if semantic.possible_questions:
                lines.append("Possible questions:")
                for question in semantic.possible_questions[:8]:
                    lines.append(f" - {question}")
            if semantic.business_keywords:
                lines.append("Keywords: " + ", ".join(semantic.business_keywords[:20]))

        if table.relationships_from:
            lines.append("Relationships:")
            for rel in table.relationships_from:
                target_schema = f"{rel.referenced_schema}." if rel.referenced_schema else ""
                lines.append(
                    f" - {rel.column_name} -> {target_schema}{rel.referenced_table_name}.{rel.referenced_column_name}"
                )

        return "\n".join(lines)

    @staticmethod
    def _column_id_for_name(table: DatabaseTable, column_name: str) -> int | None:
        for column in table.columns or []:
            if column.name == column_name:
                return column.id
        return None

    def _protected_column_label(
        self,
        table: DatabaseTable,
        column_name: str,
        pii_map: dict[int, ColumnSemantic] | None,
    ) -> str:
        column_id = self._column_id_for_name(table, column_name)
        if column_id is not None and self._should_mask_column(column_id, pii_map):
            return "[PII PROTECTED]"
        return column_name

    def _build_relationship_text(
        self,
        table: DatabaseTable,
        pii_map: dict[int, ColumnSemantic] | None = None,
    ) -> str:
        if not table.relationships_from:
            return (
                f"Table {table.schema.name}.{table.name} has no discovered foreign key relationships."
            )

        lines = [f"Relationship graph for {table.schema.name}.{table.name}:"]
        for rel in table.relationships_from:
            target_schema = f"{rel.referenced_schema}." if rel.referenced_schema else ""
            constraint = f" ({rel.constraint_name})" if rel.constraint_name else ""
            source_column = self._protected_column_label(table, rel.column_name, pii_map)
            lines.append(
                f" - {source_column} joins to {target_schema}{rel.referenced_table_name}.{rel.referenced_column_name}{constraint}"
            )
        return "\n".join(lines)

    def _build_prompt_text(self, table: DatabaseTable, semantic: Optional[SchemaSemantic]) -> str:
        prompts: List[str] = []
        questions = semantic.possible_questions if semantic else []

        if questions:
            prompts.extend(questions[:10])
        else:
            prompts.extend(
                [
                    f"What are the most important trends in {table.schema.name}.{table.name}?",
                    f"Show a summary of records for {table.schema.name}.{table.name}.",
                    f"Which columns in {table.schema.name}.{table.name} are best for grouping and filtering?",
                ]
            )

        if table.relationships_from:
            prompts.append(
                f"How does {table.schema.name}.{table.name} connect to related tables through foreign keys?"
            )

        if semantic and semantic.business_keywords:
            prompts.append(
                f"Find business patterns around {', '.join(semantic.business_keywords[:5])} in {table.name}."
            )

        return "\n".join(f" - {item}" for item in prompts)

    def _build_package_text(
        self,
        database: ConnectedDatabase,
        table: DatabaseTable,
        governance: GovernancePackage | None,
        semantic_package: SemanticPackage | None,
        relationship_packages: list[RelationshipPackage],
    ) -> tuple[str, str, str]:
        governance_bits = []
        if governance:
            governance_bits.extend([
                f"Governance summary: {governance.table_summary or ''}",
                f"Business purpose: {governance.business_purpose or ''}",
                f"PII columns: {', '.join(item.get('column_name', '') for item in governance.pii_columns[:10])}",
            ])
        semantic_bits = []
        if semantic_package:
            semantic_bits.extend([
                f"Business domain: {semantic_package.business_domain or ''}",
                f"Semantic summary: {semantic_package.semantic_summary or ''}",
                f"Business entities: {', '.join(semantic_package.business_entities[:10])}",
                f"Business processes: {', '.join(semantic_package.business_processes[:10])}",
                f"Business capabilities: {', '.join(semantic_package.business_capabilities[:10])}",
            ])
        relationship_bits = []
        relevant_relationships = [
            package for package in relationship_packages
            if package.cluster_id and table.name in package.cluster_id
        ]
        for package in relevant_relationships[:3]:
            relationship_bits.append(
                f"Relationship cluster {package.cluster_id}: {package.cluster_summary or ''}"
            )
        governance_text = "\n".join(bit for bit in governance_bits if bit)
        semantic_text = "\n".join(bit for bit in semantic_bits if bit)
        relationship_text = "\n".join(bit for bit in relationship_bits if bit)
        return governance_text, semantic_text, relationship_text

    
    async def _sync_embedding_row(
        self,
        table_id: int,
        embedding_model: str,
        vector_id: str,
        status: EmbeddingStatus,
        embedded_text: Optional[str] = None,
    ) -> SchemaEmbedding:
        result = await self.db.execute(
            select(SchemaEmbedding).where(SchemaEmbedding.table_id == table_id)
        )
        row = result.scalars().first()
        if row is None:
            row = SchemaEmbedding(
                table_id=table_id,
                embedding_model=embedding_model,
                vector_id=vector_id,
                embedding_status=status,
                embedded_text=embedded_text,
            )
            self.db.add(row)
        else:
            row.embedding_model = embedding_model
            row.vector_id = vector_id
            row.embedding_status = status
            row.generated_at = datetime.now(timezone.utc)
            if embedded_text is not None:
                row.embedded_text = embedded_text
        await safe_flush(self.db)
        return row

    def _delete_vectors_for_table(self, database_id: int, table_id: int) -> None:
        client = get_qdrant_client()
        if qmodels is None:
            raise ImportError("qdrant-client is required for vector indexing and retrieval")

        query_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(key="database_id", match=qmodels.MatchValue(value=database_id)),
                qmodels.FieldCondition(key="table_id", match=qmodels.MatchValue(value=table_id)),
            ]
        )
        for collection_name in EMBEDDING_COLLECTIONS:
            client.delete(
                collection_name=collection_name,
                points_selector=qmodels.FilterSelector(filter=query_filter),
            )

    def _payload_base(
        self,
        database: ConnectedDatabase,
        table: DatabaseTable,
        collection_name: str,
        text: str,
    ) -> Dict[str, Any]:
        return {
            "database_id": database.id,
            "database_name": database.name,
            "db_type": database.db_type.value,
            "schema_id": table.schema_id,
            "schema_name": table.schema.name,
            "table_id": table.id,
            "table_name": table.name,
            "table_type": table.table_type.value,
            "collection_name": collection_name,
            "text": truncate(text, 4000),
            "embedding_model": settings.azure_openai_embedding_deployment,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _point_id(self, collection_name: str, database_id: int, table_id: int) -> str:
        return _stable_point_id(collection_name, database_id, table_id)

    async def _upsert_document(self, artifact: EmbeddingArtifact) -> None:
        client = get_qdrant_client()
        if qmodels is None:
            raise ImportError("qdrant-client is required for vector indexing and retrieval")

        client.upsert(
            collection_name=artifact.collection_name,
            points=[
                qmodels.PointStruct(
                    id=artifact.point_id,
                    vector=artifact.vector,
                    payload=artifact.payload,
                )
            ],
        )

    @_traceable("generate_database_embeddings", run_type="chain")
    async def generate_database_embeddings(self, database_id: int) -> EmbeddingBatchResult:
        start = time.perf_counter()
        if not package_is_enabled("rag"):
            raise ValueError("RAG package is disabled by registry")
        database = await self._fetch_database(database_id)
        tables = await self._fetch_tables(database_id)

        if not tables:
            raise ValueError(f"Database {database_id} has no tables to index")

        self._ensure_collections()

        batch_result = EmbeddingBatchResult(
            database_id=database.id,
            database_name=database.name,
            embedding_model=settings.azure_openai_embedding_deployment,
        )

        total_vectors = 0
        aggregated_usage: Dict[str, int] = {}

        for table in tables:
            table_start = time.monotonic()
            try:
                table_result = await self.generate_table_embeddings(database_id, table.id)
                _log_stage_duration(
                    "embedding generation / table",
                    table_start,
                    database_id=database_id,
                    table_id=table.id,
                    table_name=table.name,
                )
            except Exception as exc:
                logger.exception(
                    "Failed to index table_id=%s for db_id=%s: %s",
                    table.id,
                    database_id,
                    exc,
                )
                await self._sync_embedding_row(
                    table_id=table.id,
                    embedding_model=settings.azure_openai_embedding_deployment,
                    vector_id=self._point_id(COLLECTION_SCHEMA_TABLES, database_id, table.id),
                    status=EmbeddingStatus.failed,
                    embedded_text=None,
                )
                batch_result.success = False
                continue

            total_vectors += table_result.vectors_indexed
            batch_result.tables_indexed += 1
            batch_result.success = batch_result.success and table_result.success
            for key, value in table_result.token_usage.items():
                aggregated_usage[key] = aggregated_usage.get(key, 0) + value

        batch_result.vectors_indexed = total_vectors
        batch_result.token_usage = aggregated_usage
        batch_result.latency_ms = (time.perf_counter() - start) * 1000
        batch_result.message = f"Indexed {batch_result.tables_indexed} tables into {total_vectors} vectors"

        logger.info(
            "Generated embeddings for db_id=%s in %.2fms (%d tables, %d vectors)",
            database_id,
            batch_result.latency_ms,
            batch_result.tables_indexed,
            batch_result.vectors_indexed,
        )
        return batch_result

    @_traceable("generate_table_embeddings", run_type="chain")
    async def generate_table_embeddings(self, database_id: int, table_id: int) -> EmbeddingBatchResult:
        start = time.perf_counter()
        if not package_is_enabled("rag"):
            raise ValueError("RAG package is disabled by registry")
        database = await self._fetch_database(database_id)
        table = await self._fetch_table(table_id)
        semantic = await self._fetch_semantic_summary(table_id)
        pii_map = await self._fetch_pii_map(database_id)
        governance_packages = await self._fetch_governance_packages(database_id)
        semantic_package = await self._fetch_semantic_package(database_id)
        relationship_packages = await self._fetch_relationship_packages(database_id)
        package_governance = governance_packages.get(table.id)

        table_text = self._build_table_text(table, semantic, pii_map)
        relationship_text = self._build_relationship_text(table, pii_map)
        prompt_text = self._build_prompt_text(table, semantic)
        governance_text, semantic_text, relationship_package_text = self._build_package_text(
            database, table, package_governance, semantic_package, relationship_packages
        )
        if governance_text:
            table_text = "\n\n".join([table_text, governance_text])
        if semantic_text:
            prompt_text = "\n\n".join([prompt_text, semantic_text])
        if relationship_package_text:
            relationship_text = "\n\n".join([relationship_text, relationship_package_text])

        texts = [table_text, relationship_text, prompt_text]
        vectors, usage = await self._embed_texts(
            texts,
            database_id=database_id,
            database_name=database.name,
            table_name=table.name,
            artifact_type="schema_embedding",
        )
        self._ensure_collections(len(vectors[0]))
        qdrant_stage_start = time.monotonic()

        point_ids = {
            COLLECTION_SCHEMA_TABLES: self._point_id(COLLECTION_SCHEMA_TABLES, database_id, table_id),
            COLLECTION_SCHEMA_RELATIONSHIPS: self._point_id(COLLECTION_SCHEMA_RELATIONSHIPS, database_id, table_id),
            COLLECTION_SCHEMA_PROMPTS: self._point_id(COLLECTION_SCHEMA_PROMPTS, database_id, table_id),
        }

        await self._sync_embedding_row(
            table_id=table_id,
            embedding_model=settings.azure_openai_embedding_deployment,
            vector_id=point_ids[COLLECTION_SCHEMA_TABLES],
            status=EmbeddingStatus.running,
        )

        self._delete_vectors_for_table(database_id, table_id)
        _log_stage_duration("qdrant upsert / delete previous vectors", qdrant_stage_start, database_id=database_id, table_id=table_id)

        artifacts = [
            EmbeddingArtifact(
                collection_name=COLLECTION_SCHEMA_TABLES,
                point_id=point_ids[COLLECTION_SCHEMA_TABLES],
                text=table_text,
                payload={
                    **self._payload_base(database, table, COLLECTION_SCHEMA_TABLES, table_text),
                    "column_names": [
                        self._protected_column_label(table, column.name, pii_map)
                        for column in table.columns
                    ],
                    "relationships": [
                        f"{self._protected_column_label(table, rel.column_name, pii_map)}->{rel.referenced_table_name}.{rel.referenced_column_name}"
                        for rel in table.relationships_from
                    ],
                    "semantic_summary": semantic.semantic_summary if semantic else None,
                    "possible_questions": semantic.possible_questions if semantic else [],
                },
                vector=vectors[0],
            ),
            EmbeddingArtifact(
                collection_name=COLLECTION_SCHEMA_RELATIONSHIPS,
                point_id=point_ids[COLLECTION_SCHEMA_RELATIONSHIPS],
                text=relationship_text,
                payload={
                    **self._payload_base(database, table, COLLECTION_SCHEMA_RELATIONSHIPS, relationship_text),
                    "relationships": [
                        {
                            "column_name": self._protected_column_label(table, rel.column_name, pii_map),
                            "referenced_schema": rel.referenced_schema,
                            "referenced_table_name": rel.referenced_table_name,
                            "referenced_column_name": rel.referenced_column_name,
                            "constraint_name": rel.constraint_name,
                        }
                        for rel in table.relationships_from
                    ],
                },
                vector=vectors[1],
            ),
            EmbeddingArtifact(
                collection_name=COLLECTION_SCHEMA_PROMPTS,
                point_id=point_ids[COLLECTION_SCHEMA_PROMPTS],
                text=prompt_text,
                payload={
                    **self._payload_base(database, table, COLLECTION_SCHEMA_PROMPTS, prompt_text),
                    "prompt_context": prompt_text,
                    "possible_questions": semantic.possible_questions if semantic else [],
                },
                vector=vectors[2],
            ),
        ]

        for artifact in artifacts:
            artifact_start = time.monotonic()
            await self._upsert_document(artifact)
            _log_stage_duration(
                "qdrant upsert / document",
                artifact_start,
                database_id=database_id,
                table_id=table_id,
                collection=artifact.collection_name,
            )

        await self._sync_embedding_row(
            table_id=table_id,
            embedding_model=settings.azure_openai_embedding_deployment,
            vector_id=point_ids[COLLECTION_SCHEMA_TABLES],
            status=EmbeddingStatus.completed,
        )

        result = EmbeddingBatchResult(
            database_id=database.id,
            database_name=database.name,
            embedding_model=settings.azure_openai_embedding_deployment,
            tables_indexed=1,
            vectors_indexed=len(artifacts),
            token_usage=usage,
            latency_ms=(time.perf_counter() - start) * 1000,
            success=True,
            message=f"Indexed table {table.schema.name}.{table.name}",
        )
        logger.info(
            "Indexed table embeddings for table_id=%s in %.2fms",
            table_id,
            result.latency_ms,
        )
        return result

    async def _fetch_table(self, table_id: int) -> DatabaseTable:
        result = await self.db.execute(
            select(DatabaseTable)
            .options(
                selectinload(DatabaseTable.schema).selectinload(DatabaseSchema.connected_database),
                selectinload(DatabaseTable.columns),
                selectinload(DatabaseTable.relationships_from),
            )
            .where(DatabaseTable.id == table_id)
        )
        table = result.scalars().first()
        if not table:
            raise ValueError(f"Table {table_id} not found")
        return table

    async def get_embedding_status(self, database_id: int) -> Dict[str, Any]:
        database = await self._fetch_database(database_id)
        tables = await self._fetch_tables(database_id)

        result = await self.db.execute(
            select(SchemaEmbedding).join(DatabaseTable).join(DatabaseSchema).where(
                DatabaseSchema.connected_db_id == database_id
            )
        )
        rows = result.scalars().all()

        status_counts = {
            "pending": sum(1 for row in rows if row.embedding_status == EmbeddingStatus.pending),
            "running": sum(1 for row in rows if row.embedding_status == EmbeddingStatus.running),
            "completed": sum(1 for row in rows if row.embedding_status == EmbeddingStatus.completed),
            "failed": sum(1 for row in rows if row.embedding_status == EmbeddingStatus.failed),
        }
        last_generated_at = max((row.generated_at for row in rows), default=None)

        vector_counts = self.get_qdrant_vector_counts(database_id)
        collections = []
        total_vectors = 0
        for collection_name, vector_count in vector_counts.items():
            total_vectors += vector_count
            collections.append(
                {
                    "collection_name": collection_name,
                    "vectors": vector_count,
                    "indexed_tables": len(rows),
                    "last_indexed_at": last_generated_at,
                }
            )

        return {
            "database_id": database.id,
            "database_name": database.name,
            "embedding_model": settings.azure_openai_embedding_deployment,
            "embedding_health": self.is_embedding_ready(),
            "qdrant_health": self.is_qdrant_ready(),
            "indexed_tables": len(rows),
            "completed_tables": status_counts["completed"],
            "failed_tables": status_counts["failed"],
            "vectors_total": total_vectors,
            "vector_counts": vector_counts,
            "collections": collections,
            "last_generated_at": last_generated_at,
            "message": f"{len(rows)} table(s) have embedding records and {total_vectors} vector(s) are indexed.",
            "status_breakdown": status_counts,
            "total_tables": len(tables),
        }

    def get_qdrant_vector_counts(self, database_id: int) -> Dict[str, int]:
        if QdrantClient is None:
            return {name: 0 for name in EMBEDDING_COLLECTIONS}

        client = get_qdrant_client()
        if qmodels is None:
            return {name: 0 for name in EMBEDDING_COLLECTIONS}

        query_filter = qmodels.Filter(
            must=[qmodels.FieldCondition(key="database_id", match=qmodels.MatchValue(value=database_id))]
        )
        counts: Dict[str, int] = {}
        for collection_name in EMBEDDING_COLLECTIONS:
            try:
                counts[collection_name] = client.count(
                    collection_name=collection_name,
                    count_filter=query_filter,
                    exact=True,
                ).count
            except Exception:
                counts[collection_name] = 0
        return counts

    def is_embedding_ready(self) -> bool:
        return settings.embedding_configured

    def is_qdrant_ready(self) -> bool:
        try:
            if QdrantClient is None:
                return False
            client = get_qdrant_client()
            client.get_collections()
            return True
        except Exception:
            return False


def safe_json_loads(raw: Optional[str], default: Any) -> Any:
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default
