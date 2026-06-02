"""
Database-level Semantic Intelligence APIs.

Clean contract:
- POST /semantics/generate/{source_id}
- GET /semantics/{source_id}
- DELETE /semantics/{source_id}
- GET /semantics/{source_id}/export
"""

from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.metadata import ConnectedDatabase, DatabaseSemantic
from app.schemas.api_schemas import (
    DatabaseSemanticExportResponse,
    DatabaseSemanticGenerateResponse,
    DatabaseSemanticResponse,
)
from app.services.database_semantic_service import DatabaseSemanticService
from app.schema_engine.embeddings import _traceable
from app.utils import now_utc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/semantics", tags=["Semantic Intelligence"])


def _semantic_response(db_semantic: DatabaseSemantic) -> DatabaseSemanticResponse:
    return DatabaseSemanticResponse(
        id=db_semantic.id,
        source_id=db_semantic.source_id,
        business_domain=db_semantic.business_domain,
        business_summary=db_semantic.business_summary,
        key_entities=db_semantic.key_entities,
        business_glossary=db_semantic.business_glossary,
        suggested_use_cases=db_semantic.suggested_use_cases,
        confidence_score=db_semantic.confidence_score,
        generation_status=db_semantic.generation_status.value,
        generated_at=db_semantic.generated_at,
        created_at=db_semantic.created_at,
        updated_at=db_semantic.updated_at,
    )


@router.post(
    "/generate/{source_id}",
    response_model=DatabaseSemanticGenerateResponse,
    summary="Generate semantic intelligence for a database",
    status_code=status.HTTP_202_ACCEPTED,
)
@_traceable("api_generate_semantics", run_type="chain")
async def generate_semantics(
    source_id: int,
    db: AsyncSession = Depends(get_db),
) -> DatabaseSemanticGenerateResponse:
    result = await db.execute(select(ConnectedDatabase).where(ConnectedDatabase.id == source_id))
    database = result.scalars().first()
    if not database:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Database {source_id} not found")

    start = time.perf_counter()
    service = DatabaseSemanticService(db)

    try:
        db_semantic, duration_ms = await service.generate_and_store_semantics(source_id)
        await db.commit()
        status_value = db_semantic.generation_status.value

        if status_value == "completed":
            message = f"Semantic intelligence generated for {database.display_name or database.name}"
        elif status_value == "no_metadata":
            message = "Cannot generate semantics until the database has synced metadata."
        else:
            message = f"Semantic generation finished with status {status_value}"

        return DatabaseSemanticGenerateResponse(
            source_id=source_id,
            status=status_value,
            message=message,
            generated_at=db_semantic.generated_at,
            duration_ms=round(duration_ms or ((time.perf_counter() - start) * 1000), 2),
        )
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        logger.error("Semantic generation failed for database %d: %s", source_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate semantic intelligence",
        )


@router.get(
    "/{source_id}",
    response_model=DatabaseSemanticResponse,
    summary="Get semantic intelligence for a database",
)
async def get_semantics(
    source_id: int,
    db: AsyncSession = Depends(get_db),
) -> DatabaseSemanticResponse:
    result = await db.execute(select(ConnectedDatabase).where(ConnectedDatabase.id == source_id))
    database = result.scalars().first()
    if not database:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Database {source_id} not found")

    service = DatabaseSemanticService(db)
    db_semantic = await service.get_semantic(source_id)
    if not db_semantic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No semantic profile exists for database {source_id}",
        )

    return _semantic_response(db_semantic)


@router.delete(
    "/{source_id}",
    summary="Delete semantic intelligence for a database",
)
async def delete_semantics(
    source_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    result = await db.execute(select(ConnectedDatabase).where(ConnectedDatabase.id == source_id))
    database = result.scalars().first()
    if not database:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Database {source_id} not found")

    service = DatabaseSemanticService(db)
    deleted = await service.delete_semantic(source_id)
    await db.commit()

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No semantic profile found for database {source_id}")

    return {"status": "deleted", "message": f"Semantic profile for database {source_id} deleted successfully"}


@router.get(
    "/{source_id}/export",
    response_model=DatabaseSemanticExportResponse,
    summary="Export semantic intelligence for a database",
)
async def export_semantics(
    source_id: int,
    format: str = Query(default="json", pattern="^(json|markdown)$"),
    db: AsyncSession = Depends(get_db),
) -> DatabaseSemanticExportResponse:
    result = await db.execute(select(ConnectedDatabase).where(ConnectedDatabase.id == source_id))
    database = result.scalars().first()
    if not database:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Database {source_id} not found")

    service = DatabaseSemanticService(db)
    db_semantic = await service.get_semantic(source_id)
    if not db_semantic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No semantic profile exists for database {source_id}")

    if format.lower() == "markdown":
        content = _export_semantic_markdown(database, db_semantic)
        filename = f"{database.name}_semantics.md"
    else:
        content = json.dumps(
            {
                "database_name": database.name,
                "database_type": database.db_type.value,
                "business_domain": db_semantic.business_domain,
                "business_summary": db_semantic.business_summary,
                "key_entities": db_semantic.key_entities,
                "business_glossary": db_semantic.business_glossary,
                "suggested_use_cases": db_semantic.suggested_use_cases,
                "confidence_score": db_semantic.confidence_score,
                "generation_status": db_semantic.generation_status.value,
                "generated_at": db_semantic.generated_at.isoformat() if db_semantic.generated_at else None,
                "created_at": db_semantic.created_at.isoformat(),
                "updated_at": db_semantic.updated_at.isoformat(),
            },
            indent=2,
        )
        filename = f"{database.name}_semantics.json"
        format = "json"

    return DatabaseSemanticExportResponse(
        format=format,
        filename=filename,
        content=content,
        generated_at=now_utc(),
    )


def _export_semantic_markdown(database: ConnectedDatabase, db_semantic: DatabaseSemantic) -> str:
    content = f"""# Database Semantic Profile

**Database:** {database.name}  
**Type:** {database.db_type.value}  
**Status:** {db_semantic.generation_status.value}  
**Generated:** {db_semantic.generated_at.isoformat() if db_semantic.generated_at else 'N/A'}  
**Confidence Score:** {db_semantic.confidence_score:.1%}

## Business Domain

{db_semantic.business_domain or 'Not determined'}

## Business Summary

{db_semantic.business_summary or 'No summary available'}

## Key Entities

"""

    if db_semantic.key_entities:
        for entity in db_semantic.key_entities:
            content += f"- {entity}\n"
    else:
        content += "No key entities identified.\n"

    content += "\n## Business Glossary\n\n"

    if db_semantic.business_glossary:
        for item in db_semantic.business_glossary:
            term = item.get("term", "Unknown") if isinstance(item, dict) else str(item)
            definition = item.get("definition", "") if isinstance(item, dict) else ""
            content += f"**{term}**  \n{definition}\n\n"
    else:
        content += "No glossary entries available.\n"

    content += "## Suggested Use Cases\n\n"

    if db_semantic.suggested_use_cases:
        for use_case in db_semantic.suggested_use_cases:
            content += f"- {use_case}\n"
    else:
        content += "No use cases suggested.\n"

    content += """

---

_This semantic profile was generated by AI analysis of database metadata._
"""

    return content
