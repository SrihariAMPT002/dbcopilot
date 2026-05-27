"""
/semantic — Semantic schema enrichment endpoints.

Provides APIs for:
- Generating semantic context for tables and databases
- Retrieving stored enrichment data
- Getting AI-ready prompts
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models.metadata import ConnectedDatabase, DatabaseSchema, DatabaseTable, SchemaSemantic
from app.schema_engine.enricher import SchemaEnricher
from app.schema_engine.metrics import MetricsEngine
from app.schema_engine.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/semantic", tags=["Semantic Intelligence"])


# ── Pydantic Models ────────────────────────────────────────────────────────────

class SemanticSummaryResponse(BaseModel):
    """Response with semantic enrichment data for a table."""

    table_id: int
    table_name: str
    schema_name: str
    business_summary: str
    likely_usage: list[str]
    important_columns: list[str]
    business_keywords: list[str]
    possible_questions: list[str]
    generated_at: str

    class Config:
        from_attributes = True


class DatabaseContextResponse(BaseModel):
    """Response with schema context for a database."""

    database_id: int
    database_name: str
    context: str  # Formatted schema context prompt

    class Config:
        from_attributes = True


class SemanticContextResponse(BaseModel):
    """Response with semantic-enriched schema context."""

    database_id: int
    database_name: str
    context: str  # Formatted schema context with semantic data
    tables_enriched: int

    class Config:
        from_attributes = True


class EnrichmentMetricsResponse(BaseModel):
    """Response with enrichment operation metrics."""

    tables_processed: int
    tables_succeeded: int
    tables_failed: int
    openai_api_calls: int
    total_tokens_used: int
    duration_ms: float
    success_rate_percent: float

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


# ── POST /semantic-enrichment/run/{db_id} ─────────────────────────────────────

@router.post(
    "/enrichment/run/{database_id}",
    response_model=dict[str, Any],
    summary="Generate semantic enrichment for all tables in a database",
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_semantic_enrichment(
    database_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Generate semantic enrichment for all tables in a database using Azure OpenAI.
    
    This endpoint:
    1. Fetches all tables in the database
    2. Analyzes each table's schema
    3. Calls Azure OpenAI to generate business context
    4. Stores enrichment in schema_semantics table
    
    Returns enrichment status and metrics.
    
    Status: 202 Accepted (enrichment is asynchronous)
    """
    # Verify database exists
    result = await db.execute(
        select(ConnectedDatabase).where(ConnectedDatabase.id == database_id)
    )
    database = result.scalars().first()
    
    if not database:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database {database_id} not found",
        )

    try:
        enricher = SchemaEnricher(db)
        metrics = MetricsEngine()

        # Enrich all tables
        enrichments = await enricher.enrich_database(database_id)

        # Save enrichments
        saved_count = 0
        for enrichment in enrichments:
            try:
                await enricher.save_enrichment(db, enrichment)
                metrics.record_table_processed(success=True)
                saved_count += 1
            except Exception as e:
                logger.warning("Failed to save enrichment: %s", e)
                metrics.record_table_processed(success=False)

        await db.commit()

        summary = metrics.get_summary()
        return {
            "status": "completed",
            "database_id": database_id,
            "tables_enriched": saved_count,
            "metrics": summary,
        }

    except ValueError as exc:
        logger.error("Semantic enrichment validation error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Semantic enrichment failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Semantic enrichment failed",
        )


# ── POST /semantic-enrichment/table/{table_id} ─────────────────────────────────

@router.post(
    "/enrichment/table/{table_id}",
    response_model=SemanticSummaryResponse,
    summary="Generate semantic enrichment for a single table",
    status_code=status.HTTP_200_OK,
)
async def enrich_single_table(
    table_id: int,
    db: AsyncSession = Depends(get_db),
) -> SemanticSummaryResponse:
    """
    Generate semantic enrichment for a single table.
    
    Args:
        table_id: Primary key of the table to enrich
        
    Returns:
        Semantic enrichment data with business context
    """
    # Verify table exists
    result = await db.execute(
        select(DatabaseTable)
        .where(DatabaseTable.id == table_id)
        .options(selectinload(DatabaseTable.schema))
    )
    table = result.scalars().first()

    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table {table_id} not found",
        )

    try:
        enricher = SchemaEnricher(db)

        # Enrich and save
        enrichment = await enricher.enrich_table(table_id)
        saved_semantic = await enricher.save_enrichment(db, enrichment)
        await db.commit()

        return SemanticSummaryResponse(
            table_id=saved_semantic.table_id,
            table_name=table.name,
            schema_name=table.schema.name,
            business_summary=saved_semantic.semantic_summary,
            likely_usage=saved_semantic.likely_usage,
            important_columns=saved_semantic.important_columns,
            business_keywords=saved_semantic.business_keywords,
            possible_questions=saved_semantic.possible_questions,
            generated_at=saved_semantic.generated_at.isoformat(),
        )

    except ValueError as exc:
        logger.error("Enrichment validation error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Enrichment failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Enrichment failed",
        )


# ── GET /semantic-summary/{table_id} ───────────────────────────────────────────

@router.get(
    "/summary/{table_id}",
    response_model=SemanticSummaryResponse,
    summary="Get semantic summary for a table",
)
async def get_semantic_summary(
    table_id: int,
    db: AsyncSession = Depends(get_db),
) -> SemanticSummaryResponse:
    """
    Retrieve stored semantic enrichment for a table.
    
    Returns 404 if table has not been enriched yet.
    
    Args:
        table_id: Primary key of the table
        
    Returns:
        Stored semantic enrichment data
    """
    result = await db.execute(
        select(SchemaSemantic).where(SchemaSemantic.table_id == table_id)
    )
    semantic = result.scalars().first()

    if not semantic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No semantic enrichment found for table {table_id}",
        )

    # Fetch table for names
    result = await db.execute(
        select(DatabaseTable)
        .where(DatabaseTable.id == table_id)
        .options(selectinload(DatabaseTable.schema))
    )
    table = result.scalars().first()

    return SemanticSummaryResponse(
        table_id=semantic.table_id,
        table_name=table.name,
        schema_name=table.schema.name,
        business_summary=semantic.semantic_summary,
        likely_usage=semantic.likely_usage,
        important_columns=semantic.important_columns,
        business_keywords=semantic.business_keywords,
        possible_questions=semantic.possible_questions,
        generated_at=semantic.generated_at.isoformat(),
    )


# ── GET /semantic-context/{database_id} ────────────────────────────────────────

@router.get(
    "/context/{database_id}",
    response_model=DatabaseContextResponse,
    summary="Get schema context prompt for a database",
)
async def get_schema_context(
    database_id: int,
    db: AsyncSession = Depends(get_db),
) -> DatabaseContextResponse:
    """
    Get a formatted schema context prompt for a database.
    
    This prompt contains all tables, columns, and relationships
    ready to be sent to an LLM.
    
    Args:
        database_id: Primary key of the connected database
        
    Returns:
        Formatted schema context as a prompt
    """
    # Verify database exists
    result = await db.execute(select(ConnectedDatabase).where(ConnectedDatabase.id == database_id))
    database = result.scalars().first()

    if not database:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database {database_id} not found",
        )

    try:
        builder = PromptBuilder(db)
        context = await builder.build_database_context(database_id)

        return DatabaseContextResponse(
            database_id=database_id,
            database_name=database.display_name or database.name,
            context=context,
        )

    except Exception as exc:
        logger.error("Failed to build schema context: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to build schema context",
        )


# ── GET /semantic-context/{database_id}/with-semantics ────────────────────────

@router.get(
    "/context/{database_id}/with-semantics",
    response_model=SemanticContextResponse,
    summary="Get schema context with semantic enrichment",
)
async def get_semantic_context(
    database_id: int,
    db: AsyncSession = Depends(get_db),
) -> SemanticContextResponse:
    """
    Get a formatted schema context that includes semantic enrichment data.
    
    Combines raw schema structure with AI-generated business context
    for richer LLM prompts.
    
    Args:
        database_id: Primary key of the connected database
        
    Returns:
        Formatted schema context with semantic enrichment
    """
    # Verify database exists
    result = await db.execute(select(ConnectedDatabase).where(ConnectedDatabase.id == database_id))
    database = result.scalars().first()

    if not database:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database {database_id} not found",
        )

    try:
        builder = PromptBuilder(db)
        context = await builder.build_semantic_context(database_id)

        # Count enriched tables
        result = await db.execute(
            select(SchemaSemantic).where(SchemaSemantic.database_id == database_id)
        )
        enriched_count = len(result.scalars().all())

        return SemanticContextResponse(
            database_id=database_id,
            database_name=database.display_name or database.name,
            context=context,
            tables_enriched=enriched_count,
        )

    except Exception as exc:
        logger.error("Failed to build semantic context: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to build semantic context",
        )


# â”€â”€ GET /prompt-context/{database_id} â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get(
    "/prompt-context/{database_id}",
    response_model=DatabaseContextResponse,
    summary="Get AI-ready prompt context for a database",
)
async def get_prompt_context(
    database_id: int,
    db: AsyncSession = Depends(get_db),
) -> DatabaseContextResponse:
    return await get_schema_context(database_id, db)


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


# â”€â”€ POST /prompt/generate â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

