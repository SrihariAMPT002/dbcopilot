"""Generate embeddings for persisted prompt packages."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt_embedding import PromptEmbedding
from app.models.prompt_package import PromptPackage
from app.services.ai_observability_service import AIObservabilityService
from app.core.config import settings


class PromptEmbeddingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def embed_prompt(self, prompt_package: PromptPackage) -> PromptEmbedding:
        observability = AIObservabilityService()
        result = await observability.generate(
            operation="embeddings",
            module="prompt_studio",
            artifact_type=prompt_package.artifact_type,
            prompt_id="prompt_embedding",
            prompt_version=prompt_package.prompt_version,
            database_id=prompt_package.database_id,
            database_name=None,
            model_name=settings.azure_openai_embedding_deployment or settings.azure_openai_deployment,
            input_texts=[prompt_package.generated_prompt],
            request_kwargs={},
            extra_metadata={"feature": "prompt_embedding", "prompt_package_id": prompt_package.id},
        )
        vector = result.embeddings[0] if result.embeddings else []
        row = PromptEmbedding(
            prompt_package_id=prompt_package.id,
            embedding_model=result.model_name,
            vector=json.dumps(vector, default=str),
        )
        self.db.add(row)
        await self.db.flush()
        return row

