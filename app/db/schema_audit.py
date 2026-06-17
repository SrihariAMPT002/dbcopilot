from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from sqlalchemy import UniqueConstraint, inspect
from sqlalchemy.sql.sqltypes import Boolean, DateTime, Enum, Float, Integer, String, Text

import app.models  # noqa: F401  # ensure ORM models are registered on Base.metadata
from app.models.metadata import Base
from app.models.metadata import GovernancePackage


def _type_signature(column_type: Any) -> str:
    if isinstance(column_type, String):
        length = getattr(column_type, "length", None)
        return f"String({length})" if length else "String"
    if isinstance(column_type, Integer):
        return "Integer"
    if isinstance(column_type, Text):
        return "Text"
    if isinstance(column_type, Boolean):
        return "Boolean"
    if isinstance(column_type, Float):
        return "Float"
    if isinstance(column_type, DateTime):
        return "DateTime(timezone=True)" if getattr(column_type, "timezone", False) else "DateTime"
    if isinstance(column_type, Enum):
        return f"Enum({getattr(column_type, 'name', 'enum')})"
    return column_type.__class__.__name__


def _safe_get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _safe_columns(obj: Any) -> list[Any]:
    columns = _safe_get(obj, "columns", [])
    if isinstance(columns, Mapping):
        return list(columns.values())
    return list(columns or [])


def normalize_index(obj: Any) -> tuple[str, tuple[str, ...], bool]:
    name = str(_safe_get(obj, "name", ""))
    columns = _safe_get(obj, "column_names", None)
    if columns is None:
        columns = [getattr(col, "name", col) for col in _safe_columns(obj)]
    unique = bool(_safe_get(obj, "unique", False))
    return name, tuple(str(col) for col in columns), unique


def normalize_column(obj: Any) -> tuple[str, str, bool]:
    name = str(_safe_get(obj, "name", ""))
    column_type = _safe_get(obj, "type", _safe_get(obj, "data_type", None))
    nullable = bool(_safe_get(obj, "nullable", True))
    return name, _type_signature(column_type) if column_type is not None else "Unknown", nullable


def normalize_fk(obj: Any) -> tuple[str, tuple[str, ...], str, tuple[str, ...]]:
    name = str(_safe_get(obj, "name", ""))
    constrained_columns = tuple(str(col) for col in (_safe_get(obj, "constrained_columns", []) or []))
    referred_table = str(_safe_get(obj, "referred_table", ""))
    referred_columns = tuple(str(col) for col in (_safe_get(obj, "referred_columns", []) or []))
    if not constrained_columns and hasattr(obj, "parent") and hasattr(obj, "column"):
        constrained_columns = (str(getattr(obj.parent, "name", "")),)
        referred_table = str(getattr(getattr(obj.column, "table", None), "name", referred_table))
        referred_columns = (str(getattr(obj.column, "name", "")),)
        if not name:
            name = str(getattr(getattr(obj, "constraint", None), "name", ""))
    return name, constrained_columns, referred_table, referred_columns


def normalize_constraint(obj: Any) -> tuple[str, tuple[str, ...]]:
    name = str(_safe_get(obj, "name", ""))
    columns = _safe_get(obj, "column_names", None)
    if columns is None:
        columns = [getattr(col, "name", col) for col in _safe_columns(obj)]
    return name, tuple(str(col) for col in columns)


def _index_signature(index: Any) -> tuple[str, tuple[str, ...], bool]:
    return normalize_index(index)


def _index_columns_signature(index: Any) -> tuple[tuple[str, ...], bool]:
    _, columns, unique = normalize_index(index)
    return columns, unique


@dataclass
class SchemaAuditTableReport:
    table_name: str
    missing_columns: list[str] = field(default_factory=list)
    extra_columns: list[str] = field(default_factory=list)
    type_mismatches: list[str] = field(default_factory=list)
    missing_indexes: list[str] = field(default_factory=list)
    duplicate_indexes: list[str] = field(default_factory=list)
    missing_foreign_keys: list[str] = field(default_factory=list)
    missing_unique_constraints: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return self.has_critical_errors()

    def has_critical_errors(self) -> bool:
        return bool(self.missing_columns or self.type_mismatches or self.missing_foreign_keys)

    def has_warnings(self) -> bool:
        return bool(self.extra_columns or self.missing_indexes or self.duplicate_indexes or self.missing_unique_constraints)


@dataclass
class SchemaAuditReport:
    fixed: list[str] = field(default_factory=list)
    migration_generated: list[str] = field(default_factory=list)
    requires_manual_review: list[str] = field(default_factory=list)
    table_reports: list[SchemaAuditTableReport] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return self.has_critical_errors()

    def has_critical_errors(self) -> bool:
        return any(table.has_critical_errors() for table in self.table_reports)

    def has_warnings(self) -> bool:
        return any(table.has_warnings() for table in self.table_reports) or bool(self.requires_manual_review)

    def format_message(self) -> str:
        lines: list[str] = []
        for table in self.table_reports:
            if not table.has_critical_errors() and not table.has_warnings():
                continue
            parts: list[str] = []
            if table.missing_columns:
                parts.append(f"missing columns {', '.join(table.missing_columns)}")
            if table.type_mismatches:
                parts.append(f"type mismatches {', '.join(table.type_mismatches)}")
            if table.missing_foreign_keys:
                parts.append(f"missing foreign keys {', '.join(table.missing_foreign_keys)}")
            if table.missing_indexes:
                parts.append(f"missing indexes {', '.join(table.missing_indexes)}")
            if table.duplicate_indexes:
                parts.append(f"duplicate indexes {', '.join(table.duplicate_indexes)}")
            if table.missing_unique_constraints:
                parts.append(f"missing unique constraints {', '.join(table.missing_unique_constraints)}")
            lines.append(f"{table.table_name}: " + "; ".join(parts))
        return "Schema drift detected: " + " | ".join(lines) if lines else "Schema audit passed."


def audit_ai_model_contracts() -> list[str]:
    """Return human-readable contract issues for optional AI fields."""
    issues: list[str] = []
    required_attrs = {
        GovernancePackage: [
            "table_summary",
            "business_purpose",
            "confidence_score",
            "evidence",
            "rule_matches",
            "sample_patterns",
            "prompt_tokens",
            "completion_tokens",
            "reasoning_tokens",
            "finish_reason",
            "latency_ms",
            "prompt_id",
            "prompt_version",
            "model_name",
            "trace_id",
            "raw_failure_reason",
            "failure_reason",
        ]
    }
    for model, attrs in required_attrs.items():
        for attr in attrs:
            if not hasattr(model, attr):
                issues.append(f"{model.__name__}.{attr} is missing from the ORM contract")
    return issues


def audit_schema(sync_conn) -> SchemaAuditReport:
    inspector = inspect(sync_conn)
    report = SchemaAuditReport()
    db_tables = set(inspector.get_table_names())

    for table in Base.metadata.sorted_tables:
        table_name = table.name
        if table_name not in db_tables:
            report.table_reports.append(
                SchemaAuditTableReport(table_name=table_name, missing_columns=[f"<table missing: {table_name}>"])
            )
            continue

        db_columns = {col["name"]: col for col in inspector.get_columns(table_name)}
        model_columns = {normalize_column(col)[0]: col for col in table.columns}
        table_report = SchemaAuditTableReport(table_name=table_name)

        for column_name, column in model_columns.items():
            if column_name not in db_columns:
                table_report.missing_columns.append(column_name)
                continue
            expected_type = _type_signature(column.type)
            actual_type = _type_signature(db_columns[column_name]["type"])
            if expected_type != actual_type:
                table_report.type_mismatches.append(f"{column_name} ({actual_type} != {expected_type})")

        db_only_columns = sorted(set(db_columns) - set(model_columns))
        table_report.extra_columns.extend(db_only_columns)

        model_indexes = {normalize_index(index) for index in table.indexes}
        db_index_rows = inspector.get_indexes(table_name)
        db_indexes = {_index_signature(index) for index in db_index_rows}
        db_index_signatures = [_index_columns_signature(index) for index in db_index_rows]
        duplicate_signatures = sorted(
            {
                signature
                for signature in db_index_signatures
                if db_index_signatures.count(signature) > 1
            }
        )
        if duplicate_signatures:
            table_report.duplicate_indexes.extend(
                [f"{', '.join(columns)}{' unique' if unique else ''}" for columns, unique in duplicate_signatures]
            )
        missing_indexes = sorted(model_indexes - db_indexes)
        if missing_indexes:
            table_report.missing_indexes.extend([f"{name}({', '.join(columns)})" for name, columns, _ in missing_indexes])

        model_unique_constraints = set()
        for constraint in table.constraints:
            if isinstance(constraint, UniqueConstraint):
                model_unique_constraints.add(tuple(sorted(normalize_constraint(constraint)[1])))
        for index in table.indexes:
            if getattr(index, "unique", False):
                model_unique_constraints.add(tuple(sorted(normalize_index(index)[1])))
        db_unique_constraints = {
            tuple(sorted(constraint["column_names"]))
            for constraint in inspector.get_unique_constraints(table_name)
        }
        missing_unique = sorted(model_unique_constraints - db_unique_constraints)
        if missing_unique:
            table_report.missing_unique_constraints.extend([", ".join(columns) for columns in missing_unique])

        model_fks = set()
        for col in table.columns:
            for fk in col.foreign_keys:
                _, constrained_columns, referred_table, referred_columns = normalize_fk(fk)
                source_column = constrained_columns[0] if constrained_columns else getattr(col, "name", "")
                target_column = referred_columns[0] if referred_columns else ""
                model_fks.add((source_column, referred_table, target_column))
        db_fks = {
            (
                (fk.get("constrained_columns") or [""])[0],
                fk.get("referred_table"),
                (fk.get("referred_columns") or [""])[0],
            )
            for fk in inspector.get_foreign_keys(table_name)
        }
        missing_fks = sorted(model_fks - db_fks)
        if missing_fks:
            table_report.missing_foreign_keys.extend([f"{src}->{dst}.{col}" for src, dst, col in missing_fks])

        if table_report.extra_columns:
            report.requires_manual_review.append(f"{table_name}: extra columns {', '.join(table_report.extra_columns)}")

        report.table_reports.append(table_report)

    return report
