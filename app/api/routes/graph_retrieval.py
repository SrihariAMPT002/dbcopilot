"""Graph retrieval APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.graph_retrieval import GraphRetrievalRequest, GraphRetrievalResponse, GraphNodeItem, GraphPathItem
from app.services.graph_retrieval_service import GraphRetrievalService

router = APIRouter(prefix="/retrieval", tags=["Graph Retrieval"])


@router.post("/graph", response_model=GraphRetrievalResponse)
async def graph_retrieval(request: GraphRetrievalRequest, db: AsyncSession = Depends(get_db)) -> GraphRetrievalResponse:
    result = await GraphRetrievalService(db).retrieve(
        query=request.query,
        database_id=request.database_id,
        table_id=request.table_id,
        related_table_id=request.related_table_id,
        depth=request.depth,
        max_paths=request.max_paths,
    )
    return GraphRetrievalResponse(
        database_id=result.database_id,
        query=result.query,
        latency_ms=result.latency_ms,
        neighbors=[GraphNodeItem(**item) for item in result.neighbors],
        shortest_paths=[GraphPathItem(**item) for item in result.shortest_paths],
        contextual_retrieval=[GraphNodeItem(**item) for item in result.contextual_retrieval],
        lineage=result.lineage,
    )

