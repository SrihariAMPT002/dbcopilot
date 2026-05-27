"""
QdrantService — semantic search and collection management utility.

Does NOT generate embeddings. Works on top of vectors stored by EmbeddingEngine.
Call EmbeddingEngine to index; call QdrantService to search and manage.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

COLLECTION_SCHEMA_TABLES = "schema_tables"
COLLECTION_SCHEMA_RELATIONSHIPS = "schema_relationships"
COLLECTION_SCHEMA_PROMPTS = "schema_prompts"

ALL_COLLECTIONS = (
    COLLECTION_SCHEMA_TABLES,
    COLLECTION_SCHEMA_RELATIONSHIPS,
    COLLECTION_SCHEMA_PROMPTS,
)

_qdrant_svc: Optional["QdrantService"] = None


class QdrantService:
    """
    Thin wrapper over QdrantClient scoped to the collections created by EmbeddingEngine.

    Responsibilities:
      - Semantic search (accepts a pre-computed query vector)
      - Collection health and stats
      - Delete vectors by database_id
    """

    def __init__(self, url: str) -> None:
        from qdrant_client import QdrantClient

        self.client = QdrantClient(url=url, timeout=10)
        self._url = url
        logger.info("QdrantService connected to %s", url)

    # ── Health ────────────────────────────────────────────────────────────

    def health_check(self) -> bool:
        try:
            self.client.get_collections()
            return True
        except Exception as exc:
            logger.warning("Qdrant health check failed: %s", exc)
            return False

    # ── Stats ─────────────────────────────────────────────────────────────

    def collection_stats(self) -> Dict[str, int]:
        """Return point count per collection. Returns 0 for non-existent collections."""
        stats: Dict[str, int] = {}
        for name in ALL_COLLECTIONS:
            try:
                info = self.client.get_collection(name)
                stats[name] = info.points_count or 0
            except Exception:
                stats[name] = 0
        return stats

    def database_vector_counts(self, database_id: int) -> Dict[str, int]:
        """Return per-collection vector count filtered by database_id."""
        from qdrant_client.http import models as qmodels

        query_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="database_id",
                    match=qmodels.MatchValue(value=database_id),
                )
            ]
        )
        counts: Dict[str, int] = {}
        for name in ALL_COLLECTIONS:
            try:
                counts[name] = self.client.count(
                    collection_name=name,
                    count_filter=query_filter,
                    exact=True,
                ).count
            except Exception:
                counts[name] = 0
        return counts

    # ── Search ────────────────────────────────────────────────────────────

    def search(
        self,
        query_vector: List[float],
        collection: str = COLLECTION_SCHEMA_TABLES,
        db_id: Optional[int] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search a single collection with a pre-computed vector.

        Args:
            query_vector: Embedding of the search query (from EmbeddingEngine._embed_text).
            collection: One of ALL_COLLECTIONS.
            db_id: Optional filter — only return results from this database.
            top_k: Maximum number of results.

        Returns:
            List of dicts with 'score' plus all Qdrant payload fields.
        """
        from qdrant_client.http import models as qmodels

        if collection not in ALL_COLLECTIONS:
            raise ValueError(
                f"Unknown collection {collection!r}. Must be one of: {ALL_COLLECTIONS}"
            )

        filt = None
        if db_id is not None:
            filt = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="database_id",
                        match=qmodels.MatchValue(value=db_id),
                    )
                ]
            )

        try:
            results = self.client.search(
                collection_name=collection,
                query_vector=query_vector,
                query_filter=filt,
                limit=top_k,
                with_payload=True,
            )
            return [{"score": r.score, **r.payload} for r in results]
        except Exception as exc:
            logger.warning("Qdrant search failed on %s: %s", collection, exc)
            return []

    def search_all_collections(
        self,
        query_vector: List[float],
        db_id: Optional[int] = None,
        top_k_per_collection: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Search all collections and return merged, score-sorted results.
        Useful for broad semantic lookups across table, relationship, and prompt context.
        """
        results: List[Dict[str, Any]] = []
        for collection in ALL_COLLECTIONS:
            hits = self.search(
                query_vector=query_vector,
                collection=collection,
                db_id=db_id,
                top_k=top_k_per_collection,
            )
            for hit in hits:
                hit["_collection"] = collection
            results.extend(hits)

        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return results

    # ── Delete ────────────────────────────────────────────────────────────

    def delete_by_database(self, database_id: int) -> None:
        """Remove all vectors for a database across all collections."""
        from qdrant_client.http import models as qmodels

        query_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="database_id",
                    match=qmodels.MatchValue(value=database_id),
                )
            ]
        )
        for collection in ALL_COLLECTIONS:
            try:
                self.client.delete(
                    collection_name=collection,
                    points_selector=qmodels.FilterSelector(filter=query_filter),
                )
                logger.info("Deleted vectors from %s for database_id=%s", collection, database_id)
            except Exception as exc:
                logger.warning(
                    "Could not delete from %s for database_id=%s: %s",
                    collection,
                    database_id,
                    exc,
                )

    def delete_by_table(self, database_id: int, table_id: int) -> None:
        """Remove all vectors for a single table across all collections."""
        from qdrant_client.http import models as qmodels

        query_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="database_id",
                    match=qmodels.MatchValue(value=database_id),
                ),
                qmodels.FieldCondition(
                    key="table_id",
                    match=qmodels.MatchValue(value=table_id),
                ),
            ]
        )
        for collection in ALL_COLLECTIONS:
            try:
                self.client.delete(
                    collection_name=collection,
                    points_selector=qmodels.FilterSelector(filter=query_filter),
                )
            except Exception as exc:
                logger.warning(
                    "Could not delete table vectors from %s table_id=%s: %s",
                    collection,
                    table_id,
                    exc,
                )


# ── Singleton ─────────────────────────────────────────────────────────────────


def get_qdrant_service() -> QdrantService:
    """Return a cached QdrantService instance."""
    global _qdrant_svc
    if _qdrant_svc is None:
        from app.core.config import settings

        url = (
            settings.qdrant_url
            or f"http://{settings.qdrant_host or 'qdrant'}:{settings.qdrant_port}"
        )
        _qdrant_svc = QdrantService(url=url)
    return _qdrant_svc


def reset_qdrant_service() -> None:
    """Force re-initialisation — used in tests."""
    global _qdrant_svc
    _qdrant_svc = None