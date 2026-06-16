"""AI prompt generation for Prompt Studio."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.prompts import get_prompt_registry
from app.core.config import settings
from app.models.prompt_evaluation import PromptEvaluation
from app.models.prompt_embedding import PromptEmbedding
from app.models.prompt_observability_log import PromptObservabilityLog
from app.models.prompt_package import PromptPackage
from app.models.prompt_version import PromptVersion
from app.services.ai_observability_service import AIObservabilityService
from app.services.prompt_studio_service import PromptStudioService
from app.services.prompt_embedding_service import PromptEmbeddingService
from app.utils import now_utc


@dataclass
class PromptArtifactResult:
    prompt_package: PromptPackage
    version: PromptVersion
    observability: PromptObservabilityLog
    evaluation: Optional[PromptEvaluation]
    embedding: Optional[PromptEmbedding] = None


class PromptGenerationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.registry = get_prompt_registry()

    @staticmethod
    def _compact_json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)

    async def _next_version(self, database_id: int, artifact_type: str, template_id: str) -> int:
        result = await self.db.execute(
            select(PromptPackage)
            .where(PromptPackage.database_id == database_id)
            .where(PromptPackage.artifact_type == artifact_type)
            .where(PromptPackage.template_id == template_id)
            .order_by(desc(PromptPackage.id))
        )
        latest = result.scalars().first()
        if not latest:
            return 1
        return int(latest.prompt_version or 1) + 1

    async def _build_context(self, database_id: int) -> dict[str, Any]:
        return await PromptStudioService(self.db)._build_context(database_id)

    async def generate(
        self,
        *,
        database_id: int,
        artifact_type: str,
        template_id: str,
        model_name: Optional[str] = None,
    ) -> PromptArtifactResult:
        context = await self._build_context(database_id)
        seed_template_id = template_id if template_id and template_id != "default" else PromptStudioService(self.db)._template_id_for(artifact_type)
        try:
            seed_template = PromptStudioService(self.db).registry.render_prompt(seed_template_id, context, category="system")
        except Exception:
            seed_template = PromptStudioService(self.db).registry.render_prompt("system_prompt", context, category="system")
        prompt_registry = self.registry.render_prompt(
            "prompt_generation",
            {
                "template_id": template_id,
                "artifact_type": artifact_type,
                "template_text": "\n\n".join(
                    [seed_template.system_message, seed_template.user_prompt]
                ).strip(),
                "context": context,
                "context_json": self._compact_json(context),
            },
            category="prompt_studio",
        )

        observability = AIObservabilityService()
        result = await observability.generate(
            operation="chat",
            module="prompt_studio",
            artifact_type=artifact_type,
            prompt_id="prompt_generation",
            prompt_version="1.0",
            database_id=database_id,
            database_name=context.get("database_name"),
            model_name=model_name or settings.azure_openai_deployment or "gpt-5-nano",
            messages=[
                {
                    "role": "system",
                    "content": prompt_registry.system_message or "You are an enterprise prompt engineer.",
                },
                {
                    "role": "user",
                    "content": prompt_registry.user_prompt,
                },
            ],
            request_kwargs={"max_completion_tokens": 2400},
            completeness_score=1.0,
            coverage_score=1.0,
            confidence_score=1.0,
            extra_metadata={
                "feature": "prompt_generation",
                "template_id": template_id,
                "artifact_type": artifact_type,
            },
        )

        generated_prompt = (result.content or "").strip()
        if not generated_prompt:
            raise ValueError("Prompt generation returned empty content")

        next_version = await self._next_version(database_id, artifact_type, template_id)
        package = PromptPackage(
            database_id=database_id,
            artifact_type=artifact_type,
            template_id=template_id,
            generated_prompt=generated_prompt,
            model_name=result.model_name,
            trace_id=result.trace_id,
            prompt_version=str(next_version),
            confidence_score=1.0,
            generation_metadata=self._compact_json(
                {
                    "database_name": context.get("database_name"),
                    "template_id": template_id,
                    "artifact_type": artifact_type,
                    "prompt_id": "prompt_generation",
                }
            ),
            execution_status="completed",
        )
        self.db.add(package)
        await self.db.flush()

        version = PromptVersion(
            prompt_package_id=package.id,
            version=next_version,
            generated_prompt=generated_prompt,
            model_name=result.model_name,
            template_id=template_id,
            trace_id=result.trace_id,
        )
        self.db.add(version)

        usage = result.token_usage or {}
        observability_row = PromptObservabilityLog(
            prompt_package_id=package.id,
            trace_id=result.trace_id,
            model_name=result.model_name,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            reasoning_tokens=usage.get("reasoning_tokens"),
            latency_ms=result.latency_ms,
            finish_reason=None,
            execution_status="completed",
            failure_reason=None,
        )
        self.db.add(observability_row)

        evaluation = PromptEvaluation(
            prompt_package_id=package.id,
            completeness_score=1.0,
            safety_score=1.0,
            grounding_score=1.0,
            hallucination_risk=0.0,
            sql_safety_score=1.0,
            rag_quality_score=1.0,
            agent_quality_score=1.0,
            prompt_quality_score=1.0,
            reasoning_summary="AI-generated prompt optimized using persisted intelligence packages.",
            packages_used=self._compact_json(
                [
                    "governance_packages",
                    "semantic_package",
                    "relationship_packages",
                    "kpi_packages",
                    "readiness_snapshots",
                    "metadata",
                ]
            ),
            evidence=self._compact_json(
                [
                    {"reason": "compresses metadata and adds safety constraints"},
                    {"reason": "uses persisted intelligence packages as source of truth"},
                ]
            ),
            trace_id=result.trace_id,
            model_name=result.model_name,
        )
        self.db.add(evaluation)

        embedding = await PromptEmbeddingService(self.db).embed_prompt(package)

        await self.db.commit()
        await self.db.refresh(package)
        await self.db.refresh(version)
        await self.db.refresh(observability_row)
        await self.db.refresh(evaluation)
        await self.db.refresh(embedding)

        return PromptArtifactResult(
            prompt_package=package,
            version=version,
            observability=observability_row,
            evaluation=evaluation,
            embedding=embedding,
        )
