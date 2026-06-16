"""
MetricsEngine — Track performance and usage metrics for semantic enrichment.

Collects metrics on:
- Token usage (input/output)
- Latency (enrichment processing time)
- Error rates
- Schema complexity
- Relationship density
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentMetrics:
    """Container for enrichment operation metrics."""

    # Timing
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    latency_ms: float = 0.0

    # OpenAI API
    openai_calls: int = 0
    openai_errors: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0

    # Schema metrics
    tables_processed: int = 0
    tables_succeeded: int = 0
    tables_failed: int = 0
    relationships_analyzed: int = 0
    columns_analyzed: int = 0

    # Complexity
    avg_schema_complexity: float = 0.0
    avg_relationship_density: float = 0.0

    def complete(self):
        """Mark metrics as complete and calculate final statistics."""
        self.end_time = datetime.now(timezone.utc)
        self.latency_ms = (self.end_time - self.start_time).total_seconds() * 1000


class MetricsEngine:
    """
    Collects and tracks metrics for semantic enrichment operations.
    
    Usage:
        metrics = MetricsEngine()
        metrics.record_openai_call(0.5)  # 500ms call
        metrics.record_enrichment_latency(1.2)
        summary = metrics.get_summary()
    """

    def __init__(self):
        self.metrics = EnrichmentMetrics()
        self._latencies = []
        self._token_counts = []

    # ── OpenAI API metrics ─────────────────────────────────────────────────

    def record_openai_call(self, latency_seconds: float, input_tokens: int = 0, output_tokens: int = 0):
        """
        Record an OpenAI API call.
        
        Args:
            latency_seconds: Time taken for the API call
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens used
        """
        self.metrics.openai_calls += 1
        self._latencies.append(latency_seconds)
        
        if input_tokens > 0 or output_tokens > 0:
            self.metrics.total_input_tokens += input_tokens
            self.metrics.total_output_tokens += output_tokens
            self.metrics.total_tokens += input_tokens + output_tokens
            self._token_counts.append((input_tokens, output_tokens))

        logger.debug(
            "OpenAI call #%d: %.2fs (in: %d, out: %d tokens)",
            self.metrics.openai_calls,
            latency_seconds,
            input_tokens,
            output_tokens,
        )

    def record_openai_error(self):
        """Record an OpenAI API error."""
        self.metrics.openai_errors += 1
        logger.warning("OpenAI API error #%d", self.metrics.openai_errors)

    # ── Enrichment metrics ─────────────────────────────────────────────────

    def record_enrichment_latency(self, latency_seconds: float):
        """Record enrichment processing latency."""
        self.metrics.latency_ms = latency_seconds * 1000
        logger.debug("Enrichment latency: %.2fms", self.metrics.latency_ms)

    def record_table_processed(self, success: bool = True):
        """Record a table processed by enrichment."""
        self.metrics.tables_processed += 1
        if success:
            self.metrics.tables_succeeded += 1
        else:
            self.metrics.tables_failed += 1

    def record_schema_metrics(
        self,
        relationships_count: int = 0,
        columns_count: int = 0,
        complexity_score: float = 0.0,
        relationship_density: float = 0.0,
    ):
        """Record schema complexity metrics."""
        self.metrics.relationships_analyzed += relationships_count
        self.metrics.columns_analyzed += columns_count
        if complexity_score > 0:
            self.metrics.avg_schema_complexity = complexity_score
        if relationship_density > 0:
            self.metrics.avg_relationship_density = relationship_density

    # ── Generate summary statistics ────────────────────────────────────────

    def get_summary(self) -> dict:
        """
        Get a summary of all collected metrics.
        
        Returns:
            Dictionary with aggregated metrics and statistics
        """
        self.metrics.complete()

        avg_latency = sum(self._latencies) / len(self._latencies) if self._latencies else 0
        max_latency = max(self._latencies) if self._latencies else 0
        min_latency = min(self._latencies) if self._latencies else 0

        success_rate = (
            (self.metrics.tables_succeeded / self.metrics.tables_processed * 100)
            if self.metrics.tables_processed > 0
            else 0
        )

        return {
            "timestamp": self.metrics.start_time.isoformat(),
            "duration_ms": self.metrics.latency_ms,
            "tables": {
                "processed": self.metrics.tables_processed,
                "succeeded": self.metrics.tables_succeeded,
                "failed": self.metrics.tables_failed,
                "success_rate_percent": round(success_rate, 2),
            },
            "schema": {
                "columns_analyzed": self.metrics.columns_analyzed,
                "relationships_analyzed": self.metrics.relationships_analyzed,
                "avg_complexity_score": round(self.metrics.avg_schema_complexity, 2),
                "avg_relationship_density": round(self.metrics.avg_relationship_density, 2),
            },
            "openai": {
                "api_calls": self.metrics.openai_calls,
                "errors": self.metrics.openai_errors,
                "input_tokens_total": self.metrics.total_input_tokens,
                "output_tokens_total": self.metrics.total_output_tokens,
                "tokens_total": self.metrics.total_tokens,
                "avg_call_latency_seconds": round(avg_latency, 3),
                "max_call_latency_seconds": round(max_latency, 3),
                "min_call_latency_seconds": round(min_latency, 3),
            },
        }

    # ── Format for display ─────────────────────────────────────────────────

    def get_formatted_summary(self) -> str:
        """
        Get a human-readable summary of metrics.
        
        Returns:
            Formatted string with metrics
        """
        summary = self.get_summary()

        lines = [
            "=" * 60,
            "SEMANTIC ENRICHMENT METRICS",
            "=" * 60,
            f"Duration: {summary['duration_ms']:.2f}ms",
            "",
            "TABLES:",
            f"  Processed: {summary['tables']['processed']}",
            f"  Succeeded: {summary['tables']['succeeded']}",
            f"  Failed: {summary['tables']['failed']}",
            f"  Success Rate: {summary['tables']['success_rate_percent']}%",
            "",
            "SCHEMA ANALYSIS:",
            f"  Columns: {summary['schema']['columns_analyzed']}",
            f"  Relationships: {summary['schema']['relationships_analyzed']}",
            f"  Avg Complexity: {summary['schema']['avg_complexity_score']}",
            f"  Relationship Density: {summary['schema']['avg_relationship_density']}",
            "",
            "AZURE OPENAI:",
            f"  API Calls: {summary['openai']['api_calls']}",
            f"  Errors: {summary['openai']['errors']}",
            f"  Input Tokens: {summary['openai']['input_tokens_total']}",
            f"  Output Tokens: {summary['openai']['output_tokens_total']}",
            f"  Total Tokens: {summary['openai']['tokens_total']}",
            f"  Avg Latency: {summary['openai']['avg_call_latency_seconds']:.3f}s",
            f"  Max Latency: {summary['openai']['max_call_latency_seconds']:.3f}s",
            "=" * 60,
        ]

        return "\n".join(lines)

    # ── Calculate schema complexity ────────────────────────────────────────

    @staticmethod
    def calculate_table_complexity(table) -> float:
        """
        Calculate a complexity score for a table (0-100).
        
        Factors:
        - Number of columns (more = higher complexity)
        - Number of relationships (more = higher complexity)
        - Presence of complex types (enums, arrays, etc.)
        
        Args:
            table: DatabaseTable ORM object
            
        Returns:
            Complexity score from 0 to 100
        """
        score = 0.0

        # Base score from column count
        columns = list(getattr(table, "columns", []) or [])
        relationships = list(getattr(table, "relationships_from", []) or [])
        col_count = len(columns)
        score += min(col_count * 5, 40)  # Max 40 points

        # Bonus for relationships
        rel_count = len(relationships)
        score += min(rel_count * 10, 30)  # Max 30 points

        # Check for complex types
        if columns:
            complex_types = {"array", "json", "jsonb", "xml", "enum"}
            complex_col_count = sum(
                1 for col in columns if any(t in (getattr(col, "data_type", "") or "").lower() for t in complex_types)
            )
            score += min(complex_col_count * 5, 20)  # Max 20 points

        # Check for large tables
        if table.row_count and table.row_count > 1_000_000:
            score += 10

        return min(score, 100.0)

    @staticmethod
    def calculate_schema_relationship_density(tables) -> float:
        """
        Calculate relationship density for a schema.
        
        Density = (total_relationships) / (tables * (tables - 1) / 2)
        
        Maximum density is 1.0 (fully connected), minimum is 0.0 (no relationships).
        
        Args:
            tables: List of DatabaseTable ORM objects
            
        Returns:
            Relationship density score from 0 to 1
        """
        if len(tables) < 2:
            return 0.0

        total_relationships = 0
        for table in tables:
            total_relationships += len(getattr(table, "relationships_from", []) or [])

        # Maximum possible relationships in a complete graph
        max_relationships = len(tables) * (len(tables) - 1) / 2

        return min(total_relationships / max_relationships, 1.0) if max_relationships > 0 else 0.0
