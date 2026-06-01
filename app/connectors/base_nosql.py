"""
Base connector helpers for NoSQL schema inference.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from app.connectors.base import BaseConnector


@dataclass
class InferredFieldProfile:
    field_path: str
    inferred_data_type: str
    nested_depth: int
    is_array: bool
    occurrence_percentage: float
    schema_confidence: float
    type_distribution: dict[str, int] = field(default_factory=dict)


class BaseNoSQLConnector(BaseConnector):
    """Shared inference utilities for document-style databases."""

    @staticmethod
    def flatten_document(
        value: Any,
        parent_path: str = "",
        depth: int = 0,
        max_depth: int = 5,
    ) -> list[tuple[str, Any, int, bool]]:
        if depth > max_depth:
            return []

        rows: list[tuple[str, Any, int, bool]] = []
        if isinstance(value, dict):
            for key, child in value.items():
                path = f"{parent_path}.{key}" if parent_path else key
                rows.extend(BaseNoSQLConnector.flatten_document(child, path, depth + 1, max_depth))
        elif isinstance(value, list):
            rows.append((parent_path, value, max(depth - 1, 0), True))
            if value:
                # Infer shape from first handful of items.
                for item in value[:3]:
                    rows.extend(
                        BaseNoSQLConnector.flatten_document(
                            item, f"{parent_path}[]", depth + 1, max_depth
                        )
                    )
        else:
            rows.append((parent_path, value, max(depth - 1, 0), False))
        return rows

    @staticmethod
    def build_field_profiles(
        docs: list[dict[str, Any]],
        infer_type_fn,
    ) -> list[InferredFieldProfile]:
        total_docs = max(1, len(docs))
        field_presence: dict[str, int] = defaultdict(int)
        field_types: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        field_depth: dict[str, int] = defaultdict(int)
        field_array: dict[str, bool] = defaultdict(bool)

        for doc in docs:
            seen_in_doc: set[str] = set()
            for path, value, depth, is_array in BaseNoSQLConnector.flatten_document(doc):
                if not path:
                    continue
                seen_in_doc.add(path)
                inferred = infer_type_fn(value)
                field_types[path][inferred] += 1
                field_depth[path] = max(field_depth[path], depth)
                field_array[path] = field_array[path] or is_array
            for path in seen_in_doc:
                field_presence[path] += 1

        profiles: list[InferredFieldProfile] = []
        for path in sorted(field_types.keys()):
            distribution = dict(field_types[path])
            dominant_type = max(distribution, key=distribution.get)
            occurrence_pct = round((field_presence[path] / total_docs) * 100, 2)
            type_confidence = distribution[dominant_type] / max(1, sum(distribution.values()))
            confidence = round(min(1.0, (occurrence_pct / 100.0) * type_confidence), 4)
            profiles.append(
                InferredFieldProfile(
                    field_path=path,
                    inferred_data_type=dominant_type if len(distribution) == 1 else "mixed",
                    nested_depth=field_depth[path],
                    is_array=field_array[path],
                    occurrence_percentage=occurrence_pct,
                    schema_confidence=confidence,
                    type_distribution=distribution,
                )
            )
        return profiles
