from fastapi import APIRouter

from app.api.routes import (
    capabilities,
    connections,
    metadata,
    ai_placeholders,
    semantic,
    semantics,
    column_semantics,
    prompt_studio,
    embeddings,
    relationship_graph,
    exports,
    readiness,
    pipeline,
    artifacts,
    mongodb,
)

api_router = APIRouter()
api_router.include_router(capabilities.router)
api_router.include_router(connections.router)
api_router.include_router(metadata.router)
api_router.include_router(ai_placeholders.router)
api_router.include_router(semantic.router)
api_router.include_router(semantics.router)
api_router.include_router(column_semantics.router)
api_router.include_router(prompt_studio.router)
api_router.include_router(embeddings.router)
api_router.include_router(relationship_graph.router)
api_router.include_router(exports.router)
api_router.include_router(readiness.router)
api_router.include_router(pipeline.router)
api_router.include_router(artifacts.router)
api_router.include_router(mongodb.router)
