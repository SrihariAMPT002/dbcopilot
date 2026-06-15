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
from app.schema_engine.relationship_graph import RelationshipGraphEngine
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
        engine = RelationshipGraphEngine(db)
        database = await engine._fetch_database(1)
        tables = await engine._fetch_tables(1)
        edges = []
        for table in tables:
            for rel in table.relationships_from:
                target_id = engine._resolve_target_table_id(rel, {(t.schema.name, t.name): t for t in tables}, table.schema.name)
                if target_id is None:
                    continue
                target = next(t for t in tables if t.id == target_id)
                edges.append(
                    {
                        "source_table_id": table.id,
                        "target_table_id": target.id,
                        "source_table_name": table.name,
                        "target_table_name": target.name,
                        "source_schema_name": table.schema.name,
                        "target_schema_name": target.schema.name,
                        "relationship_type": "fk",
                        "join_columns": [{"source_column": rel.column_name, "target_column": rel.referenced_column_name}],
                        "relationship_strength": 1.0,
                        "path_depth": 1,
                        "is_circular": False,
                    }
                )

        cluster_table_ids = [table.id for table in tables if table.name in {"appointments", "patients", "doctors", "claims", "insurance_policies", "payments"}]
        if not cluster_table_ids:
            cluster_table_ids = [table.id for table in tables[:6]]

        governance_package = {}
        semantic_package = await engine._build_semantic_package(*await engine._fetch_semantics(1))
        pii_map = {}
        prompt_context = engine._build_cluster_package(
            database,
            {table.id: table for table in tables},
            [],
            cluster_table_ids,
            governance_package,
            semantic_package,
            [],
            pii_map,
            domain_name="manual",
            parent_cluster_id="manual",
        )
        prompt_context, telemetry = engine._apply_cluster_budget(prompt_context, cluster_table_ids, [])
        prompt = engine.registry.render_prompt("relationship_discovery", prompt_context, category="relationship")
        request_payload = {
            "model": settings.azure_openai_deployment,
            "messages": [
                {"role": "system", "content": prompt.system_message},
                {"role": "user", "content": prompt.user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "max_completion_tokens": 640,
            "reasoning_effort": "low",
        }

        print("CLUSTER PAYLOAD:")
        print(json.dumps(prompt_context, indent=2, default=str))
        print("RENDERED PROMPT:")
        print(prompt.user_prompt)
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
        print("PARSED JSON:")
        print(content)

        _dump("relationship_raw_response.json", raw)


if __name__ == "__main__":
    asyncio.run(main())
