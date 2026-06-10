"""
Prompt Studio artifact generation APIs.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.api_schemas import (
    PromptStudioArtifactResponse,
    PromptStudioBundleResponse,
    PromptInventoryReportResponse,
    PromptStudioTemplateListResponse,
)
from app.services.prompt_studio_service import PromptStudioService

router = APIRouter(prefix="/prompt-studio", tags=["Prompt Studio"])
logger = logging.getLogger(__name__)

_VALID_ARTIFACT_TYPES = {member.value for member in PromptStudioService._artifact_order()} | {
    member.name for member in PromptStudioService._artifact_order()
}


@router.get(
    "/inventory",
    response_model=PromptInventoryReportResponse,
    summary="Get prompt inventory and consumer report",
)
async def prompt_inventory(db: AsyncSession = Depends(get_db)) -> PromptInventoryReportResponse:
    service = PromptStudioService(db)
    try:
        return PromptInventoryReportResponse(prompts=service.prompt_inventory_report())
    except Exception as exc:
        logger.error("Prompt inventory report failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to build prompt inventory report")


@router.get(
    "/templates",
    response_model=PromptStudioTemplateListResponse,
    summary="List available Prompt Studio templates",
)
async def list_templates(db: AsyncSession = Depends(get_db)) -> PromptStudioTemplateListResponse:
    service = PromptStudioService(db)
    try:
        templates = await service.list_templates()
        return PromptStudioTemplateListResponse(templates=templates)
    except Exception as exc:
        logger.error("Prompt Studio template listing failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list templates")


@router.post(
    "/generate/{db_id}",
    response_model=PromptStudioBundleResponse,
    summary="Generate and version Prompt Studio artifacts",
)
async def generate_prompt_bundle(db_id: int, db: AsyncSession = Depends(get_db)) -> PromptStudioBundleResponse:
    service = PromptStudioService(db)
    try:
        await service.generate_artifacts(db_id)
        bundle = await service.download_bundle(db_id)
        return PromptStudioBundleResponse(
            database_id=bundle["database_id"],
            bundle_filename=bundle["bundle_filename"],
            bundle_mime=bundle["bundle_mime"],
            content=bundle["content"],
            artifacts=bundle["artifacts"],
            message="Prompt Studio artifact bundle generated successfully.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Prompt Studio generation failed for db_id=%s: %s", db_id, exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate Prompt Studio artifacts")


@router.get(
    "/preview/{db_id}/{artifact_type}",
    response_model=PromptStudioArtifactResponse,
    summary="Preview a Prompt Studio artifact",
)
async def preview_artifact(
    db_id: int,
    artifact_type: str,
    db: AsyncSession = Depends(get_db),
) -> PromptStudioArtifactResponse:
    if artifact_type not in _VALID_ARTIFACT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"artifact_type must be one of: {sorted(_VALID_ARTIFACT_TYPES)}",
        )

    service = PromptStudioService(db)
    try:
        artifact = await service.preview_artifact(db_id, artifact_type)
        return PromptStudioArtifactResponse(
            database_id=db_id,
            artifact_type=artifact.artifact_type.value,
            filename=artifact.filename,
            mime=artifact.mime,
            content=artifact.content,
            manifest=artifact.manifest,
            generated_at=artifact.generated_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/download/{db_id}/{artifact_type}",
    response_model=PromptStudioArtifactResponse,
    summary="Download the latest Prompt Studio artifact",
)
async def download_artifact(
    db_id: int,
    artifact_type: str,
    db: AsyncSession = Depends(get_db),
) -> PromptStudioArtifactResponse:
    if artifact_type not in _VALID_ARTIFACT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"artifact_type must be one of: {sorted(_VALID_ARTIFACT_TYPES)}",
        )

    service = PromptStudioService(db)
    try:
        artifact = await service.download_artifact(db_id, artifact_type)
        return PromptStudioArtifactResponse(
            database_id=db_id,
            artifact_type=artifact.artifact_type.value,
            filename=artifact.filename,
            mime=artifact.mime,
            content=artifact.content,
            manifest=artifact.manifest,
            generated_at=artifact.generated_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/download-bundle/{db_id}",
    response_model=PromptStudioBundleResponse,
    summary="Download the latest Prompt Studio bundle",
)
async def download_bundle(db_id: int, db: AsyncSession = Depends(get_db)) -> PromptStudioBundleResponse:
    service = PromptStudioService(db)
    try:
        bundle = await service.download_bundle(db_id)
        return PromptStudioBundleResponse(
            database_id=bundle["database_id"],
            bundle_filename=bundle["bundle_filename"],
            bundle_mime=bundle["bundle_mime"],
            content=bundle["content"],
            artifacts=bundle["artifacts"],
            message=bundle["message"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Prompt Studio bundle download failed for db_id=%s: %s", db_id, exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to download Prompt Studio bundle")
