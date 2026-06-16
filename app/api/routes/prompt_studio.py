"""
Prompt Studio artifact generation APIs.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.schemas.api_schemas import (
    PromptGenerationRequest,
    PromptOptimizationRequest,
    PromptEvaluationRequest,
    PromptGenerationResponse,
    PromptPackageListResponse,
    PromptPackageResponse,
    PromptVersionListResponse,
    PromptVersionResponse,
    PromptObservabilityListResponse,
    PromptObservabilityLogResponse,
    PromptEvaluationResponse,
    PromptStudioArtifactResponse,
    PromptStudioBundleResponse,
    PromptInventoryReportResponse,
    PromptStudioTemplateListResponse,
)
from app.models.prompt_package import PromptPackage
from app.models.prompt_version import PromptVersion
from app.models.prompt_observability_log import PromptObservabilityLog
from app.models.prompt_evaluation import PromptEvaluation
from app.services.prompt_generation_service import PromptGenerationService
from app.services.prompt_optimizer_service import PromptOptimizerService
from app.services.prompt_evaluator_service import PromptEvaluatorService
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


@router.post(
    "/generate",
    response_model=PromptGenerationResponse,
    summary="Generate a production-grade prompt using AI",
)
async def generate_prompt(
    request: PromptGenerationRequest,
    db: AsyncSession = Depends(get_db),
) -> PromptGenerationResponse:
    try:
        result = await PromptGenerationService(db).generate(
            database_id=request.database_id,
            artifact_type=request.artifact_type,
            template_id=request.template_id,
        )
        return PromptGenerationResponse(
            generated_prompt=result.prompt_package.generated_prompt,
            model=result.prompt_package.model_name or "unknown",
            trace_id=result.prompt_package.trace_id,
            artifact_id=result.prompt_package.id,
            prompt_id=result.prompt_package.template_id,
            prompt_version=result.prompt_package.prompt_version,
            generated_at=result.prompt_package.created_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Prompt Studio AI generation failed for db_id=%s: %s", request.database_id, exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate prompt")


@router.post(
    "/optimize",
    response_model=PromptGenerationResponse,
    summary="Optimize an existing prompt package",
)
async def optimize_prompt(
    request: PromptOptimizationRequest,
    db: AsyncSession = Depends(get_db),
) -> PromptGenerationResponse:
    try:
        result = await PromptOptimizerService(db).optimize(request.prompt_package_id)
        return PromptGenerationResponse(
            generated_prompt=result.optimized_prompt,
            model=result.model_name,
            trace_id=result.trace_id,
            artifact_id=None,
            prompt_id=str(request.prompt_package_id),
            prompt_version="optimized",
            generated_at=None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Prompt optimization failed for db_id=%s: %s", request.database_id, exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to optimize prompt")


@router.post(
    "/evaluate",
    response_model=PromptEvaluationResponse,
    summary="Evaluate a prompt package",
)
async def evaluate_prompt(
    request: PromptEvaluationRequest,
    db: AsyncSession = Depends(get_db),
) -> PromptEvaluationResponse:
    try:
        result = await PromptEvaluatorService(db).evaluate(request.prompt_package_id)
        ev = result.evaluation
        return PromptEvaluationResponse(
            id=ev.id,
            prompt_package_id=ev.prompt_package_id,
            completeness_score=ev.completeness_score,
            safety_score=ev.safety_score,
            grounding_score=ev.grounding_score,
            hallucination_risk=ev.hallucination_risk,
            sql_safety_score=ev.sql_safety_score,
            rag_quality_score=ev.rag_quality_score,
            agent_quality_score=ev.agent_quality_score,
            prompt_quality_score=ev.prompt_quality_score,
            reasoning_summary=ev.reasoning_summary,
            packages_used=ev.packages_used,
            evidence=ev.evidence,
            trace_id=ev.trace_id,
            model_name=ev.model_name,
            created_at=ev.created_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Prompt evaluation failed for db_id=%s: %s", request.database_id, exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to evaluate prompt")


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


@router.get(
    "/{db_id}",
    response_model=PromptPackageListResponse,
    summary="List persisted prompt packages for a database",
)
async def list_prompt_packages(db_id: int, db: AsyncSession = Depends(get_db)) -> PromptPackageListResponse:
    result = await db.execute(
        select(PromptPackage).where(PromptPackage.database_id == db_id).order_by(PromptPackage.created_at.desc())
    )
    packages = result.scalars().all()
    return PromptPackageListResponse(
        database_id=db_id,
        prompt_packages=[
            PromptPackageResponse(
                id=row.id,
                database_id=row.database_id,
                artifact_type=row.artifact_type,
                template_id=row.template_id,
                generated_prompt=row.generated_prompt,
                model_name=row.model_name,
                trace_id=row.trace_id,
                prompt_version=row.prompt_version,
                confidence_score=row.confidence_score,
                generation_metadata=row.generation_metadata,
                execution_status=row.execution_status,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in packages
        ],
    )


@router.get(
    "/{prompt_package_id}/versions",
    response_model=PromptVersionListResponse,
    summary="List prompt versions",
)
async def list_prompt_versions(prompt_package_id: int, db: AsyncSession = Depends(get_db)) -> PromptVersionListResponse:
    result = await db.execute(
        select(PromptVersion).where(PromptVersion.prompt_package_id == prompt_package_id).order_by(PromptVersion.version.desc())
    )
    versions = result.scalars().all()
    return PromptVersionListResponse(
        prompt_package_id=prompt_package_id,
        versions=[
            PromptVersionResponse(
                id=row.id,
                prompt_package_id=row.prompt_package_id,
                version=row.version,
                generated_prompt=row.generated_prompt,
                model_name=row.model_name,
                template_id=row.template_id,
                trace_id=row.trace_id,
                created_at=row.created_at,
            )
            for row in versions
        ],
    )


@router.get(
    "/{prompt_package_id}/observability",
    response_model=PromptObservabilityListResponse,
    summary="List prompt observability logs",
)
async def list_prompt_observability(
    prompt_package_id: int, db: AsyncSession = Depends(get_db)
) -> PromptObservabilityListResponse:
    result = await db.execute(
        select(PromptObservabilityLog)
        .where(PromptObservabilityLog.prompt_package_id == prompt_package_id)
        .order_by(PromptObservabilityLog.created_at.desc())
    )
    rows = result.scalars().all()
    return PromptObservabilityListResponse(
        prompt_package_id=prompt_package_id,
        observability_logs=[
            PromptObservabilityLogResponse(
                id=row.id,
                prompt_package_id=row.prompt_package_id,
                trace_id=row.trace_id,
                model_name=row.model_name,
                prompt_tokens=row.prompt_tokens,
                completion_tokens=row.completion_tokens,
                reasoning_tokens=row.reasoning_tokens,
                latency_ms=row.latency_ms,
                finish_reason=row.finish_reason,
                execution_status=row.execution_status,
                failure_reason=row.failure_reason,
                created_at=row.created_at,
            )
            for row in rows
        ],
    )
