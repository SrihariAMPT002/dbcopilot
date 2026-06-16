"""Business glossary extraction for semantics."""

from __future__ import annotations

from typing import Any


class BusinessGlossaryService:
    def build_glossary(self, *, business_entities: list[str], business_processes: list[str], business_capabilities: list[str]) -> list[dict[str, Any]]:
        terms: list[dict[str, Any]] = []
        for entity in business_entities[:20]:
            terms.append({"term": entity, "definition": f"Core business entity related to {entity.lower()}", "source": "ai"})
        for process in business_processes[:20]:
            terms.append({"term": process, "definition": f"Business process associated with {process.lower()}", "source": "ai"})
        for capability in business_capabilities[:20]:
            terms.append({"term": capability, "definition": f"Business capability supporting {capability.lower()}", "source": "ai"})
        seen = set()
        unique: list[dict[str, Any]] = []
        for item in terms:
            if item["term"] in seen:
                continue
            seen.add(item["term"])
            unique.append(item)
        return unique

