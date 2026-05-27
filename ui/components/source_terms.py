"""
UI terminology helpers for database-agnostic rendering.

These helpers keep the Streamlit pages flexible across SQL and NoSQL sources
without changing the backend contract.
"""

from __future__ import annotations

from typing import Dict


SQL_TYPES = {"postgresql", "mysql", "sqlserver"}
NOSQL_TYPES = {"mongodb"}


def source_family(db_type: str) -> str:
    key = (db_type or "").lower().strip()
    if key in SQL_TYPES:
        return "SQL"
    if key in NOSQL_TYPES:
        return "NoSQL"
    return "Unknown"


def is_nosql(db_type: str) -> bool:
    return source_family(db_type) == "NoSQL"


def is_sql(db_type: str) -> bool:
    return source_family(db_type) == "SQL"


def terminology(db_type: str) -> Dict[str, str]:
    """
    Return display labels for the current source type.
    """

    if is_nosql(db_type):
        return {
            "database_label": "Database",
            "schema_label": "Database",
            "container_label": "Collection",
            "entity_label": "Collection",
            "field_label": "Field",
            "relationship_label": "Inferred Relationship",
            "extraction_mode": "Document sampling + inferred schema",
            "inference_mode": "NoSQL inference",
        }

    return {
        "database_label": "Database",
        "schema_label": "Schema",
        "container_label": "Table",
        "entity_label": "Table",
        "field_label": "Column",
        "relationship_label": "FK Relationship",
        "extraction_mode": "Schema introspection",
        "inference_mode": "Native metadata",
    }


def badge_label(db_type: str) -> str:
    family = source_family(db_type)
    if family == "SQL":
        return "SQL"
    if family == "NoSQL":
        return "NoSQL"
    return "Unknown"


def source_mode_text(db_type: str) -> str:
    terms = terminology(db_type)
    return f"{terms['inference_mode']} · {terms['extraction_mode']}"
