"""
Text-to-SQL Pipeline — future implementation stub.

This module defines the interface that the AI layer will implement.
The schema context is already available via the metadata store.

Planned architecture:
  1. SchemaRetriever   — fetch relevant schema from Qdrant (semantic search)
  2. SQLGenerator      — LLM generates SQL given schema context + user query
  3. SQLValidator      — validate SQL syntax and safety (no destructive ops)
  4. SQLExecutor       — run validated SQL against the external DB (read-only)
  5. ResultExplainer   — LLM generates natural language explanation of results
"""

from typing import Any, Dict, List, Optional


class TextToSQLPipeline:
    """
    Placeholder for the full text-to-SQL pipeline.

    Will use LangGraph for stateful, multi-step agent execution.
    """

    def __init__(self, db_id: int) -> None:
        self.db_id = db_id

    async def run(self, natural_language_query: str) -> Dict[str, Any]:
        """
        Execute the full pipeline:
          NL query → schema context → SQL → validation → execution → explanation

        Returns:
          {
            "sql": "SELECT ...",
            "explanation": "This query counts...",
            "results": [...],
            "columns": [...],
            "chart_hint": "bar"        # future: chart type suggestion
          }
        """
        raise NotImplementedError(
            "TextToSQLPipeline is not yet implemented. "
            "Schema context is ready in the metadata store. "
            "Activate the AI layer to enable this feature."
        )


class SchemaEmbedder:
    """
    Placeholder for schema embedding workflow.

    Will serialize schema metadata to text, embed via OpenAI/local model,
    and store vectors in Qdrant for semantic retrieval.
    """

    def __init__(self, db_id: int) -> None:
        self.db_id = db_id

    async def embed(self) -> int:
        """
        Embed all schema metadata for a connected database.
        Returns the number of vectors stored.
        """
        raise NotImplementedError("SchemaEmbedder requires Qdrant and an embedding model.")


class QueryValidator:
    """
    Placeholder for SQL safety validation.

    Will check:
      - SQL syntax validity
      - Read-only (no INSERT/UPDATE/DELETE/DROP/TRUNCATE)
      - No system table access
      - Query complexity limits
    """

    FORBIDDEN_KEYWORDS = frozenset({
        "INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE",
        "ALTER", "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE",
    })

    @classmethod
    def is_safe(cls, sql: str) -> tuple[bool, Optional[str]]:
        """
        Basic static safety check (available now — no AI needed).

        Returns: (is_safe, reason_if_unsafe)
        """
        upper = sql.upper()
        for keyword in cls.FORBIDDEN_KEYWORDS:
            # Simple word-boundary check
            import re
            if re.search(rf"\\b{keyword}\\b", upper):
                return False, f"Forbidden SQL keyword: {keyword}"
        return True, None
