"""Agent memory and query history APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.agent_memory import (
    AgentMemoryCreate,
    AgentMemoryHistoryResponse,
    AgentMemoryResponse,
    AgentMemorySearchRequest,
    AgentMemorySearchResponse,
    AgentMemorySearchHit,
)
from app.services.agent_memory_service import AgentMemoryService

router = APIRouter(prefix="/agent-memory", tags=["Agent Memory"])


@router.post("", response_model=AgentMemoryResponse)
async def create_memory(request: AgentMemoryCreate, db: AsyncSession = Depends(get_db)) -> AgentMemoryResponse:
    row = await AgentMemoryService(db).record_memory(
        database_id=request.database_id,
        query_text=request.query_text,
        response_text=request.response_text,
        context_json=request.context_json,
        memory_type=request.memory_type,
        tags=request.tags,
        trace_id=request.trace_id,
    )
    return AgentMemoryResponse(
        id=row.id,
        database_id=row.database_id,
        query_text=row.query_text,
        response_text=row.response_text,
        context_json=request.context_json,
        memory_type=row.memory_type,
        tags=request.tags,
        embedding_model=row.embedding_model,
        vector_id=row.vector_id,
        trace_id=row.trace_id,
        created_at=row.created_at.isoformat() if row.created_at else None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


@router.get("/{database_id}", response_model=AgentMemoryHistoryResponse)
async def history(database_id: int, limit: int = 20, db: AsyncSession = Depends(get_db)) -> AgentMemoryHistoryResponse:
    payload = await AgentMemoryService(db).get_history(database_id, limit=limit)
    return AgentMemoryHistoryResponse(**payload)


@router.post("/search", response_model=AgentMemorySearchResponse)
async def search(request: AgentMemorySearchRequest, db: AsyncSession = Depends(get_db)) -> AgentMemorySearchResponse:
    payload = await AgentMemoryService(db).search_history(request.database_id, request.query, top_k=request.top_k)
    return AgentMemorySearchResponse(
        database_id=payload["database_id"],
        query=payload["query"],
        total_hits=payload["total_hits"],
        results=[AgentMemorySearchHit(**item) for item in payload["results"]],
    )
