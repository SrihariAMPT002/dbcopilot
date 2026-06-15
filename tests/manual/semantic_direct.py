from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.manual._bootstrap import load_repo_env
load_repo_env()

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services.database_semantic_service import DatabaseSemanticService
from openai import AzureOpenAI


OUT_DIR = Path("tests/manual/output")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _dump(name: str, payload: object) -> Path:
    path = OUT_DIR / name
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


async def main() -> None:
    client = AzureOpenAI(
        api_key=settings.azure_openai_key,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.azure_openai_endpoint,
    )

    async with AsyncSessionLocal() as db:
        service = DatabaseSemanticService(db)
        database = await service._fetch_database_with_metadata(1)
        if database is None:
            raise RuntimeError("database_id=1 not found")
        semantic_input = await service._build_semantic_input(database)
        prompt_vars = service._build_prompt_variables(database, semantic_input)
        rendered = service.registry.render_prompt("system_prompt", prompt_vars, category="system")
        request_payload = {
            "model": settings.azure_openai_deployment,
            "messages": [
                {"role": "system", "content": rendered.system_message},
                {"role": "user", "content": rendered.user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "max_completion_tokens": 1200,
            "reasoning_effort": "low",
        }

        print("RENDERED PROMPT:")
        print(rendered.user_prompt)
        print("REQUEST PAYLOAD:")
        print(json.dumps(request_payload, indent=2, default=str))

        response = await asyncio.to_thread(client.chat.completions.create, **request_payload)
        raw = response.model_dump() if hasattr(response, "model_dump") else dict(response)
        choices = raw.get("choices", [{}])
        finish_reason = choices[0].get("finish_reason")
        usage = raw.get("usage", {})
        content = choices[0].get("message", {}).get("content", "")

        print("RAW AZURE RESPONSE:")
        print(json.dumps(raw, indent=2, default=str))
        print("FINISH REASON:", finish_reason)
        print("TOKEN USAGE:", json.dumps(usage, indent=2, default=str))
        print("PARSED SEMANTIC PAYLOAD:")
        print(content)

        _dump("semantic_raw_response.json", raw)


if __name__ == "__main__":
    asyncio.run(main())
