"""
Artifact registry APIs for versioned AI context packages.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.api_schemas import (
    ArtifactContentResponse,
    ArtifactExportResponse,
    ArtifactListResponse,
    ArtifactManifestItem,
    ArtifactManifestResponse,
)
from app.services.artifact_service import ArtifactService

router = APIRouter(prefix="/artifacts", tags=["Artifacts"])
logger = logging.getLogger(__name__)


@router.get(
    "/{db_id}",
    response_model=ArtifactListResponse,
    summary="List versioned artifacts for a database",
)
async def list_artifacts(db_id: int, db: AsyncSession = Depends(get_db)) -> ArtifactListResponse:
    service = ArtifactService(db)
    try:
        records = await service.list_artifacts(db_id)
        return ArtifactListResponse(
            database_id=db_id,
            artifacts=[
                ArtifactManifestItem(
                    id=item.id,
                    artifact_type=item.artifact_type.value,
                    version=item.version,
                    schema_hash=item.schema_hash,
                    export_status=item.export_status.value,
                    artifact_path=item.artifact_path,
                    generated_at=item.generated_at,
                )
                for item in records
            ],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Artifact list failed for db_id=%s: %s", db_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list artifacts",
        )


@router.post(
    "/{db_id}/export",
    response_model=ArtifactExportResponse,
    summary="Generate a versioned AI context package export",
)
async def export_artifacts(db_id: int, db: AsyncSession = Depends(get_db)) -> ArtifactExportResponse:
    service = ArtifactService(db)
    try:
        manifests = await service.export_artifacts(db_id)
        return ArtifactExportResponse(
            database_id=db_id,
            manifests=manifests,
            message=f"Generated {len(manifests)} versioned artifacts for database {db_id}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Artifact export failed for db_id=%s: %s", db_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export artifacts",
        )


@router.get(
    "/{db_id}/manifest",
    response_model=ArtifactManifestResponse,
    summary="Get artifact manifest and lineage for a database",
)
async def get_artifact_manifest(db_id: int, db: AsyncSession = Depends(get_db)) -> ArtifactManifestResponse:
    service = ArtifactService(db)
    try:
        payload = await service.get_manifest(db_id)
        latest = {
            key: ArtifactManifestItem(**value)
            for key, value in payload.get("latest", {}).items()
        }
        history = {
            key: [ArtifactManifestItem(**entry) for entry in entries]
            for key, entries in payload.get("history", {}).items()
        }
        return ArtifactManifestResponse(
            database_id=db_id,
            artifact_count=payload.get("artifact_count", 0),
            latest=latest,
            history=history,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Artifact manifest failed for db_id=%s: %s", db_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve artifact manifest",
        )


@router.get(
    "/{db_id}/content/{artifact_type}",
    response_model=ArtifactContentResponse,
    summary="Get stored artifact content for a database and artifact type",
)
async def get_artifact_content(
    db_id: int,
    artifact_type: str,
    version: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> ArtifactContentResponse:
    service = ArtifactService(db)
    try:
        from app.models.artifact_manifest import ArtifactType

        artifact_enum = ArtifactType.resolve(artifact_type)
        payload = await service.get_artifact_content(db_id, artifact_enum, version=version)
        return ArtifactContentResponse(**payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error(
            "Artifact content retrieval failed for db_id=%s type=%s version=%s: %s",
            db_id,
            artifact_type,
            version,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve artifact content",
        )
