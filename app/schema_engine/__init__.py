"""
Schema engine package.

Keeps the existing semantic enrichment helpers available and exports the new
embedding / retrieval layer added in Phase 2.
"""

from app.schema_engine.embeddings import (
    COLLECTION_SCHEMA_PROMPTS,
    COLLECTION_SCHEMA_RELATIONSHIPS,
    COLLECTION_SCHEMA_TABLES,
    EMBEDDING_COLLECTIONS,
    EmbeddingBatchResult,
    EmbeddingEngine,
)
from app.schema_engine.enricher import SchemaEnricher
from app.schema_engine.metrics import MetricsEngine
from app.schema_engine.prompt_builder import PromptBuilder
from app.schema_engine.retrieval import RetrievalEngine, RetrievalHit, RetrievalResult
from app.schema_engine.relationship_graph import (
    RelationshipGraphEngine,
    RelationshipGraphSnapshot,
    NeighborGraphSnapshot,
    JoinPathsSnapshot,
    ExportBundle,
)

__all__ = [
    "PromptBuilder",
    "MetricsEngine",
    "SchemaEnricher",
    "EmbeddingEngine",
    "EmbeddingBatchResult",
    "RetrievalEngine",
    "RetrievalHit",
    "RetrievalResult",
    "RelationshipGraphEngine",
    "RelationshipGraphSnapshot",
    "NeighborGraphSnapshot",
    "JoinPathsSnapshot",
    "ExportBundle",
    "COLLECTION_SCHEMA_TABLES",
    "COLLECTION_SCHEMA_RELATIONSHIPS",
    "COLLECTION_SCHEMA_PROMPTS",
    "EMBEDDING_COLLECTIONS",
]
