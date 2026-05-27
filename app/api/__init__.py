from fastapi import APIRouter

from app.api.routes import (
    connections,
    metadata,
    ai_placeholders,
    semantic,
)

# Note: embeddings, relationship_graph, and exports temporarily disabled
# These are Phase 2+ features that need integration testing.
# They will be re-enabled after core table loading is verified.

api_router = APIRouter()
api_router.include_router(connections.router)
api_router.include_router(metadata.router)
api_router.include_router(ai_placeholders.router)
api_router.include_router(semantic.router)
