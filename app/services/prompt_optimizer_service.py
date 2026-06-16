"""Prompt optimization utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.prompt_package import PromptPackage
from app.models.prompt_version import PromptVersion
from app.services.prompt_embedding_service import PromptEmbeddingService
from app.services.ai_observability_service import AIObservabilityService
from app.services.prompt_studio_service import PromptStudioService


@dataclass
class PromptOptimizationResult:
    optimized_prompt: str
    model_name: str
    trace_id: Optional[str]
    optimization_score: float
    optimization_notes: str


class PromptOptimizerService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def optimize(self, package_id: int) -> PromptOptimizationResult:
        package = await self.db.get(PromptPackage, package_id)
        if not package:
            raise ValueError(f"Prompt package {package_id} not found")
        context = await PromptStudioService(self.db)._build_context(package.database_id)
        observability = AIObservabilityService()
        result = await observability.generate(
            operation="chat",
            module="prompt_studio",
            artifact_type=package.artifact_type,
            prompt_id="prompt_optimization",
            prompt_version="1.0",
            database_id=package.database_id,
            database_name=context.get("database_name"),
            model_name=settings.azure_openai_deployment or "gpt-5-nano",
            messages=[
                {
                    "role": "system",
                    "content": "You optimize prompts for safety, grounding, and token efficiency. Return only the improved prompt text.",
                },
                {
                    "role": "user",
                    "content": "\n\n".join(
                        [
                            f"Existing prompt:\n{package.generated_prompt}",
                            f"Database context:\n{context.get('database_name')}",
                        ]
                    ),
                },
            ],
            request_kwargs={},
            extra_metadata={"feature": "prompt_optimization", "prompt_package_id": package_id},
        )
        optimized = (result.content or "").strip() or package.generated_prompt
        existing = await self.db.execute(
            select(PromptVersion)
            .where(PromptVersion.prompt_package_id == package.id)
            .order_by(desc(PromptVersion.version))
        )
        latest = existing.scalars().first()
        next_version = (latest.version if latest else int(package.prompt_version or 1)) + 1
        self.db.add(
            PromptVersion(
                prompt_package_id=package.id,
                version=next_version,
                generated_prompt=optimized,
                model_name=result.model_name,
                template_id=package.template_id,
                trace_id=result.trace_id,
            )
        )
        package.generated_prompt = optimized
        package.model_name = result.model_name
        package.trace_id = result.trace_id
        package.prompt_version = str(next_version)
        package.execution_status = "completed"
        await PromptEmbeddingService(self.db).embed_prompt(package)
        await self.db.commit()
        return PromptOptimizationResult(
            optimized_prompt=optimized,
            model_name=result.model_name,
            trace_id=result.trace_id,
            optimization_score=1.0 if optimized != package.generated_prompt else 0.75,
            optimization_notes="Optimized with AI prompt intelligence." if optimized != package.generated_prompt else "No change.",
        )
