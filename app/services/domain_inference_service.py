"""Domain inference for semantic intelligence."""

from __future__ import annotations

from typing import Any


class DomainInferenceService:
    def infer(self, *, governance_package: dict[str, Any], relationship_context: list[dict[str, Any]], statistics: dict[str, Any]) -> dict[str, float]:
        text = " ".join(
            [
                str(governance_package.get("business_domain") or ""),
                str(governance_package.get("database_id") or ""),
                " ".join(str(item.get("table_name") or "") for item in governance_package.get("packages", [])),
                " ".join(str(item.get("source_table") or "") for item in relationship_context),
                " ".join(str(item.get("target_table") or "") for item in relationship_context),
            ]
        ).lower()
        scores = {
            "healthcare": 0.0,
            "insurance": 0.0,
            "financial_services": 0.0,
            "retail": 0.0,
            "general": 0.2,
        }
        keywords = {
            "healthcare": ["health", "patient", "doctor", "clinic", "hospital", "diagnosis", "medical", "provider"],
            "insurance": ["insurance", "policy", "claim", "premium", "coverage", "underwriting"],
            "financial_services": ["bank", "loan", "payment", "invoice", "billing", "transaction", "account", "upi", "iban"],
            "retail": ["order", "product", "cart", "customer", "catalog", "sku"],
        }
        for domain, terms in keywords.items():
            hits = sum(1 for term in terms if term in text)
            scores[domain] = min(1.0, 0.15 * hits + (0.1 if statistics else 0.0))
        return scores

    def pick(self, scores: dict[str, float]) -> str:
        return max(scores.items(), key=lambda item: item[1])[0].replace("_", " ").title()

