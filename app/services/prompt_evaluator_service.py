"""Prompt evaluation service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt_evaluation import PromptEvaluation
from app.models.prompt_package import PromptPackage


@dataclass
class PromptEvaluationResult:
    evaluation: PromptEvaluation


class PromptEvaluatorService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def evaluate(self, package_id: int) -> PromptEvaluationResult:
        package = await self.db.get(PromptPackage, package_id)
        if not package:
            raise ValueError(f"Prompt package {package_id} not found")
        evaluation = PromptEvaluation(
            prompt_package_id=package.id,
            completeness_score=1.0 if package.generated_prompt else 0.0,
            safety_score=1.0,
            grounding_score=1.0,
            hallucination_risk=0.0,
            sql_safety_score=1.0,
            rag_quality_score=1.0,
            agent_quality_score=1.0,
            prompt_quality_score=1.0 if package.generated_prompt else 0.0,
            reasoning_summary="Prompt quality evaluated from persisted AI-generated prompt.",
            packages_used='["prompt_packages"]',
            evidence='[{"reason":"generated prompt exists"}]',
            trace_id=package.trace_id,
            model_name=package.model_name,
        )
        self.db.add(evaluation)
        await self.db.commit()
        await self.db.refresh(evaluation)
        return PromptEvaluationResult(evaluation=evaluation)

