"""
Prompt-context utilities for AI-ready database prompts.

This module intentionally keeps the legacy /semantic prefix for prompt tooling
while the database semantic intelligence contract lives under /semantics.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.metadata import ConnectedDatabase
from app.schema_engine.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/semantic", tags=["Prompt Context"])


class DatabaseContextResponse(BaseModel):
    """Response with schema context for a database."""

    database_id: int
    database_name: str
    context: str

    class Config:
        from_attributes = True


class PromptGenerateRequest(BaseModel):
    database_id: int
    template: str = "default"


class PromptGenerateResponse(BaseModel):
    database_id: int
    database_name: str
    template: str
    prompt: str
    token_estimate: int
    prompt_length: int
    context_type: str = "schema_context"


def _build_prompt_for_template(template: str, database_name: str, context: str) -> str:
    template = (template or "default").lower()
    if template == "concise":
        return f"Database: {database_name}\n\n{context[:4000]}"
    if template == "detailed":
        return (
            f"Database: {database_name}\n\n"
            f"{context}\n\n"
            "Use this schema context to reason about joins, business terms, and analytics use cases."
        )
    if template == "analytics":
        return (
            f"Analytics prompt for {database_name}\n\n"
            f"{context}\n\n"
            "Focus on revenue, trends, KPIs, customer behavior, and operational reporting."
        )
    if template == "retrieval":
        return (
            f"Retrieval prompt for {database_name}\n\n"
            f"{context}\n\n"
            "Prioritize schema search, table linking, and prompt-context reuse."
        )
    return context


@router.get(
    "/prompt-context/{database_id}",
    response_model=DatabaseContextResponse,
    summary="Get AI-ready prompt context for a database",
)
async def get_prompt_context(
    database_id: int,
    db: AsyncSession = Depends(get_db),
) -> DatabaseContextResponse:
    result = await db.execute(select(ConnectedDatabase).where(ConnectedDatabase.id == database_id))
    database = result.scalars().first()
    if not database:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database {database_id} not found",
        )

    builder = PromptBuilder(db)
    context = await builder.build_database_context(database_id)
    return DatabaseContextResponse(
        database_id=database_id,
        database_name=database.display_name or database.name,
        context=context,
    )


@router.post(
    "/prompt/generate",
    response_model=PromptGenerateResponse,
    summary="Generate an AI-ready schema prompt package",
)
async def generate_prompt(
    req: PromptGenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> PromptGenerateResponse:
    result = await db.execute(select(ConnectedDatabase).where(ConnectedDatabase.id == req.database_id))
    database = result.scalars().first()
    if not database:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database {req.database_id} not found",
        )

    builder = PromptBuilder(db)
    context = await builder.build_semantic_context(req.database_id)
    prompt = _build_prompt_for_template(req.template, database.display_name or database.name, context)
    token_estimate = max(1, int(len(prompt.split()) * 1.33))
    return PromptGenerateResponse(
        database_id=req.database_id,
        database_name=database.display_name or database.name,
        template=req.template,
        prompt=prompt,
        token_estimate=token_estimate,
        prompt_length=len(prompt),
    )
