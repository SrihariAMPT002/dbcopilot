"""
AI placeholder routes.

These endpoints exist to define the API contract for the future AI layer.
They currently return informative "coming soon" responses, but the
architecture is ready to receive real implementations.

Future capabilities:
  - Text-to-SQL (LLM + schema context)
  - SQL validation agent
  - Result explanation / insights
  - Conversational memory (Redis / LangGraph)
  - Chart generation hints
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.api_schemas import (
    ChatRequest,
    ChatResponse,
    GenerateSQLRequest,
    GenerateSQLResponse,
)

router = APIRouter(prefix="/ai", tags=["AI (Coming Soon)"])
logger = logging.getLogger(__name__)


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="[PLACEHOLDER] Chat with a connected database using natural language",
)
async def chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """
    Placeholder for the conversational AI layer.

    Future implementation will:
      1. Load schema context from metadata store
      2. Embed schema (Qdrant)
      3. Run LangGraph agent (planner → SQL generator → validator → executor)
      4. Return results + AI-generated insights
    """
    logger.info("AI chat placeholder hit for db_id=%s", req.db_id)
    return ChatResponse(
        message=(
            "🚀 AI querying is not yet enabled. "
            "Your database schema has been indexed and will be used as context once "
            "the AI layer is activated."
        ),
        conversation_id=req.conversation_id or "placeholder-session-001",
    )


@router.post(
    "/generate-sql",
    response_model=GenerateSQLResponse,
    summary="[PLACEHOLDER] Convert natural language to SQL",
)
async def generate_sql(
    req: GenerateSQLRequest,
    db: AsyncSession = Depends(get_db),
) -> GenerateSQLResponse:
    """
    Placeholder for Text-to-SQL generation.

    Future implementation will:
      1. Retrieve relevant schema context via semantic search (Qdrant)
      2. Pass NL query + schema to OpenAI / local LLM
      3. Validate generated SQL (syntax + safety check)
      4. Return SQL + natural language explanation
    """
    logger.info(
        "AI SQL generation placeholder hit for db_id=%s, query=%r",
        req.db_id,
        req.natural_language_query[:80],
    )
    return GenerateSQLResponse(
        message=(
            "🚀 Text-to-SQL is not yet enabled. "
            "The schema context is ready — AI SQL generation will be activated in a future release."
        )
    )
