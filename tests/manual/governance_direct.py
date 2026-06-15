from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.manual._bootstrap import load_repo_env
load_repo_env()

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.metadata import ConnectedDatabase
from app.services.column_semantic_service import ColumnSemanticService
from openai import AzureOpenAI
from sqlalchemy import select


OUT_DIR = Path("tests/manual/output")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _dump(name: str, payload: object) -> Path:
    path = OUT_DIR / name
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def _render_prompt(service: ColumnSemanticService, table, database, semantic):
    prompt_context = service._metadata_package(table, database, semantic, columns=table.columns)
    prompt = service.registry.render_prompt(service.PROMPT_ID, prompt_context, category="semantic")
    return prompt, prompt_context


async def main() -> None:
    client = AzureOpenAI(
        api_key=settings.azure_openai_key,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.azure_openai_endpoint,
    )

    async with AsyncSessionLocal() as db:
        service = ColumnSemanticService(db)
        result = await db.execute(
            select(ConnectedDatabase)
            .where(ConnectedDatabase.id == 1)
            .options()
        )
        database = result.scalars().first()
        if database is None:
            raise RuntimeError("database_id=1 not found")

        table = SimpleNamespace(
            name="appointments",
            description="",
            schema=SimpleNamespace(name="public"),
            columns=[
                SimpleNamespace(name="appointment_id", data_type="int", is_primary_key=True, is_foreign_key=False, is_nullable=False, description=""),
                SimpleNamespace(name="patient_id", data_type="int", is_primary_key=False, is_foreign_key=True, is_nullable=False, description=""),
                SimpleNamespace(name="doctor_id", data_type="int", is_primary_key=False, is_foreign_key=True, is_nullable=False, description=""),
                SimpleNamespace(name="appointment_date", data_type="timestamp", is_primary_key=False, is_foreign_key=False, is_nullable=False, description=""),
                SimpleNamespace(name="consultation_type", data_type="varchar", is_primary_key=False, is_foreign_key=False, is_nullable=True, description=""),
                SimpleNamespace(name="status", data_type="varchar", is_primary_key=False, is_foreign_key=False, is_nullable=True, description=""),
                SimpleNamespace(name="diagnosis_summary", data_type="text", is_primary_key=False, is_foreign_key=False, is_nullable=True, description=""),
            ],
        )
        semantic = await service._fetch_database_semantic(database.id)
        prompt, prompt_context = _render_prompt(service, table, database, semantic)
        request_payload = {
            "model": settings.azure_openai_deployment,
            "messages": [
                {"role": "system", "content": prompt.system_message},
                {"role": "user", "content": prompt.user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "max_completion_tokens": 384,
            "reasoning_effort": "low",
        }

        print("RAW PROMPT:")
        print(prompt.user_prompt)
        print("REQUEST PAYLOAD:")
        print(json.dumps(request_payload, indent=2, default=str))

        response = await asyncio.to_thread(client.chat.completions.create, **request_payload)
        raw = response.model_dump() if hasattr(response, "model_dump") else dict(response)
        finish_reason = raw.get("choices", [{}])[0].get("finish_reason")
        usage = raw.get("usage", {})
        content = raw.get("choices", [{}])[0].get("message", {}).get("content", "")

        print("RAW RESPONSE:")
        print(json.dumps(raw, indent=2, default=str))
        print("FINISH REASON:", finish_reason)
        print("TOKEN USAGE:", json.dumps(usage, indent=2, default=str))
        print("PARSED JSON:")
        print(content)

        _dump("governance_raw_response.json", raw)


if __name__ == "__main__":
    asyncio.run(main())
