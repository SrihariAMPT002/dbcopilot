"""
Embedding generation and semantic search endpoints.

POST /embeddings/generate/{db_id}             — embed all tables in a database
POST /embeddings/generate/{db_id}/{table_id}  — embed a single table
GET  /embeddings/status/{db_id}               — coverage + health report
DELETE /embeddings/{db_id}                    — wipe all vectors for a database
POST /embeddings/search                       — semantic search over stored vectors
"""
from __future__ import annotations

import logging
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Response

from app.db import get_db
from app.models.metadata import (
    DatabaseSchema,
    DatabaseTable,
    EmbeddingStatus,
    SchemaEmbedding,
)
from app.schema_engine.embeddings import (
    COLLECTION_SCHEMA_PROMPTS,
    COLLECTION_SCHEMA_RELATIONSHIPS,
    COLLECTION_SCHEMA_TABLES,
    EmbeddingEngine,
)
from app.schemas.embedding_schemas import (
    CollectionStatus,
    EmbeddingGenerateResponse,
    EmbeddingStatusResponse,
    SemanticSearchHit,
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from app.services.qdrant_service import get_qdrant_service
from app.utils import safe_flush

router = APIRouter(tags=["Embeddings"])
logger = logging.getLogger(__name__)

_VALID_COLLECTIONS = {
    COLLECTION_SCHEMA_TABLES,
    COLLECTION_SCHEMA_RELATIONSHIPS,
    COLLECTION_SCHEMA_PROMPTS,
    "all",
}


def _format_relationship(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return str(value)

    source_column = value.get("column_name") or value.get("source_column") or value.get("column") or "unknown"
    target_schema = f"{value.get('referenced_schema')}." if value.get("referenced_schema") else ""
    target_table = value.get("referenced_table_name") or value.get("table_name") or "unknown"
    target_column = value.get("referenced_column_name") or value.get("target_column") or "unknown"
    constraint = f" ({value.get('constraint_name')})" if value.get("constraint_name") else ""
    return f"{source_column} -> {target_schema}{target_table}.{target_column}{constraint}"


def _normalize_relationships(raw: Any) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [_format_relationship(item) for item in raw]
    return [_format_relationship(raw)]


# ── Generate ──────────────────────────────────────────────────────────────────


@router.post(
    "/embeddings/generate/{db_id}",
    response_model=EmbeddingGenerateResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate embeddings for every table in a database",
    description=(
        "Runs the full embedding pipeline: builds enriched text representations for each "
        "table (schema summary, relationship context, prompt context), calls Azure OpenAI "
        "embeddings, and upserts vectors into Qdrant. Idempotent — re-running only updates "
        "tables whose semantic summaries have changed."
    ),
)
async def generate_database_embeddings(
    db_id: int,
    db: AsyncSession = Depends(get_db),
) -> EmbeddingGenerateResponse:
    engine = EmbeddingEngine(db)
    _guard_embedding_config(engine)
    try:
        logger.info("Embedding generation started for db_id=%s", db_id)
        result = await engine.generate_database_embeddings(db_id)
        logger.info(
            "Embedding generation completed for db_id=%s in %.2fms (%d tables, %d vectors)",
            db_id,
            result.latency_ms,
            result.tables_indexed,
            result.vectors_indexed,
        )
        return EmbeddingGenerateResponse(
            database_id=result.database_id,
            database_name=result.database_name,
            embedding_model=result.embedding_model,
            tables_indexed=result.tables_indexed,
            vectors_indexed=result.vectors_indexed,
            token_usage=result.token_usage,
            latency_ms=round(result.latency_ms, 2),
            success=result.success,
            message=result.message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Embedding pipeline failed for db_id=%s: %s", db_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Embedding generation failed: {exc}",
        )


@router.post(
    "/embeddings/generate/{db_id}/{table_id}",
    response_model=EmbeddingGenerateResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate embeddings for a single table",
)
async def generate_table_embeddings(
    db_id: int,
    table_id: int,
    db: AsyncSession = Depends(get_db),
) -> EmbeddingGenerateResponse:
    engine = EmbeddingEngine(db)
    _guard_embedding_config(engine)
    try:
        result = await engine.generate_table_embeddings(db_id, table_id)
        return EmbeddingGenerateResponse(
            database_id=result.database_id,
            database_name=result.database_name,
            embedding_model=result.embedding_model,
            tables_indexed=result.tables_indexed,
            vectors_indexed=result.vectors_indexed,
            token_usage=result.token_usage,
            latency_ms=round(result.latency_ms, 2),
            success=result.success,
            message=result.message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error(
            "Table embedding failed for table_id=%s db_id=%s: %s",
            table_id, db_id, exc, exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Table embedding failed: {exc}",
        )


# ── Status ────────────────────────────────────────────────────────────────────


@router.get(
    "/embeddings/status/{db_id}",
    response_model=EmbeddingStatusResponse,
    summary="Embedding coverage and health report for a database",
)
async def get_embedding_status(
    db_id: int,
    db: AsyncSession = Depends(get_db),
) -> EmbeddingStatusResponse:
    engine = EmbeddingEngine(db)
    try:
        data = await engine.get_embedding_status(db_id)
        collections = [CollectionStatus(**c) for c in data.pop("collections", [])]
        return EmbeddingStatusResponse(**data, collections=collections)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Status check failed for db_id=%s: %s", db_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve embedding status",
        )


# ── Delete ────────────────────────────────────────────────────────────────────


@router.delete(
    "/embeddings/{db_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_database_embeddings(
    db_id: int,
    db: AsyncSession = Depends(get_db),
):
    engine = EmbeddingEngine(db)

    try:
        await engine._fetch_database(db_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    try:
        qdrant = get_qdrant_service()
        qdrant.delete_by_database(db_id)

        table_id_subq = (
            select(DatabaseTable.id)
            .join(DatabaseSchema)
            .where(DatabaseSchema.connected_db_id == db_id)
            .scalar_subquery()
        )

        await db.execute(
            update(SchemaEmbedding)
            .where(SchemaEmbedding.table_id.in_(table_id_subq))
            .values(
                embedding_status=EmbeddingStatus.pending,
                vector_id=None,
                embedded_text=None,
            )
        )

        await safe_flush(db)

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except Exception as exc:
        logger.error(
            "Delete embeddings failed for db_id=%s: %s",
            db_id,
            exc,
            exc_info=True,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete embeddings",
        )


# ── Semantic search ───────────────────────────────────────────────────────────


@router.post(
    "/embeddings/search",
    response_model=SemanticSearchResponse,
    summary="Semantic search over schema context vectors",
    description=(
        "Embeds the query with Azure OpenAI then searches Qdrant. "
        "Searches a single collection or all three (schema_tables, schema_relationships, schema_prompts) "
        "when collection='all'."
    ),
)
async def semantic_search(
    request: SemanticSearchRequest,
    db: AsyncSession = Depends(get_db),
) -> SemanticSearchResponse:
    if request.collection not in _VALID_COLLECTIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"collection must be one of: {sorted(_VALID_COLLECTIONS)}",
        )

    engine = EmbeddingEngine(db)
    _guard_embedding_config(engine)
    _guard_qdrant(engine)

    try:
        logger.info(
            "Semantic search started for db_id=%s collection=%s top_k=%s",
            request.db_id,
            request.collection,
            request.top_k,
        )
        query_vector, _ = await engine._embed_text(request.query)
    except Exception as exc:
        logger.error("Query embedding failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Azure OpenAI embedding call failed: {exc}",
        )

    qdrant = get_qdrant_service()

    try:
        if request.collection == "all":
            raw = qdrant.search_all_collections(
                query_vector=query_vector,
                db_id=request.db_id,
                top_k_per_collection=request.top_k,
            )
            result_collection_label = "all"
        else:
            raw = qdrant.search(
                query_vector=query_vector,
                collection=request.collection,
                db_id=request.db_id,
                top_k=request.top_k,
            )
            result_collection_label = request.collection
    except Exception as exc:
        logger.error("Qdrant search failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vector search failed: {exc}",
        )

    hits: List[SemanticSearchHit] = []
    for item in raw:
        known_fields = {
            "score", "database_id", "database_name", "schema_name",
            "table_name", "table_type", "text", "semantic_summary",
            "column_names", "relationships", "collection_name", "_collection",
        }
        extra = {k: v for k, v in item.items() if k not in known_fields}
        hits.append(
            SemanticSearchHit(
                score=round(float(item.get("score", 0.0)), 4),
                database_id=item.get("database_id", 0),
                database_name=item.get("database_name", ""),
                schema_name=item.get("schema_name", ""),
                table_name=item.get("table_name", ""),
                table_type=item.get("table_type", "table"),
                text=item.get("text", ""),
                semantic_summary=item.get("semantic_summary"),
                column_names=item.get("column_names") or [],
                relationships=_normalize_relationships(item.get("relationships")),
                collection_name=item.get("collection_name") or item.get("_collection", request.collection),
                extra=extra,
            )
        )

    logger.info(
        "Semantic search completed for db_id=%s collection=%s hits=%d",
        request.db_id,
        result_collection_label,
        len(hits),
    )

    return SemanticSearchResponse(
        query=request.query,
        collection=result_collection_label,
        db_id=request.db_id,
        total_results=len(hits),
        results=hits,
    )


# ── Guards ────────────────────────────────────────────────────────────────────


def _guard_embedding_config(engine: EmbeddingEngine) -> None:
    if not engine.is_embedding_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Azure OpenAI embeddings not configured. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY.",
        )


def _guard_qdrant(engine: EmbeddingEngine) -> None:
    if not engine.is_qdrant_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Qdrant vector store is not reachable. Check QDRANT_HOST or QDRANT_URL.",
        )
