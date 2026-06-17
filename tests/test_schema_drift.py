from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import Column, Index, Integer, MetaData, String, Table, UniqueConstraint, create_engine, text

from app.db import init_db as init_db_module
from app.db import schema_audit
from app.models.pipeline_execution import PipelineExecution, StageExecution
from app.models.readiness_snapshot import ReadinessSnapshot


def test_stage_execution_model_includes_blocking_column() -> None:
    assert "blocked_by_stage" in StageExecution.__table__.columns
    assert "pipeline_context_json" in PipelineExecution.__table__.columns
    assert "generated_at" in ReadinessSnapshot.__table__.columns


def test_schema_audit_detects_missing_stage_columns_indexes_and_constraints(monkeypatch: pytest.MonkeyPatch) -> None:
    metadata = MetaData()
    Table(
        "stage_executions",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("pipeline_execution_id", Integer, nullable=False),
        Column("database_id", Integer, nullable=False),
        Column("stage_name", String(64), nullable=False),
        Column("status", String(32), nullable=False),
        Column("start_time", String),
        Column("end_time", String),
        Column("error_message", String),
        Column("blocked_by_stage", String(64)),
        Column("execution_order", Integer),
        Index("ix_stage_executions_blocked_by_stage", "blocked_by_stage"),
        Index("ix_stage_executions_status", "status"),
        UniqueConstraint("stage_name", name="uq_stage_executions_stage_name"),
    )

    monkeypatch.setattr(schema_audit, "Base", SimpleNamespace(metadata=metadata))

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE stage_executions (
                id INTEGER PRIMARY KEY,
                pipeline_execution_id INTEGER NOT NULL,
                database_id INTEGER NOT NULL,
                stage_name VARCHAR(64) NOT NULL,
                status VARCHAR(32) NOT NULL,
                start_time VARCHAR,
                end_time VARCHAR,
                error_message VARCHAR,
                execution_order INTEGER
            )
            """
        ))
        conn.execute(text("CREATE INDEX ix_stage_executions_status ON stage_executions (status)"))

        report = schema_audit.audit_schema(conn)

    assert report.has_critical_errors()
    table_report = next(item for item in report.table_reports if item.table_name == "stage_executions")
    assert "blocked_by_stage" in table_report.missing_columns
    assert table_report.missing_unique_constraints
    assert table_report.missing_indexes


def test_validate_schema_drift_fails_on_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    report = SimpleNamespace(
        has_critical_errors=lambda: False,
        has_warnings=lambda: True,
        requires_manual_review=[],
        table_reports=[],
        format_message=lambda: "Schema drift detected: stage_executions missing indexes",
    )
    monkeypatch.setattr(init_db_module, "audit_schema", lambda _conn: report)
    monkeypatch.setattr(init_db_module, "audit_ai_model_contracts", lambda: [])
    monkeypatch.setattr(init_db_module, "settings", SimpleNamespace(strict_schema_validation=True))

    with pytest.raises(RuntimeError, match="Schema drift detected"):
        init_db_module._validate_schema_drift(object())


def test_pipeline_executions_schema_drift_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    metadata = MetaData()
    Table(
        "pipeline_executions",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("database_id", Integer, nullable=False),
        Column("status", String(32), nullable=False),
        Column("start_time", String),
        Column("end_time", String),
        Column("duration_seconds", Integer),
        Column("trace_id", String(255)),
        Column("model_name", String(255)),
        Column("token_usage_json", String),
        Column("pipeline_context_json", String),
        Column("context_source", String(32)),
        Column("used_context", String(8)),
        Column("fallback_reason", String),
        Column("error_message", String),
        Column("triggered_by", String(255)),
        Column("created_at", String),
        Column("updated_at", String),
        Index("ix_pipeline_executions_database_id", "database_id"),
        Index("ix_pipeline_executions_status", "status"),
    )

    monkeypatch.setattr(schema_audit, "Base", SimpleNamespace(metadata=metadata))

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE pipeline_executions (
                    id INTEGER PRIMARY KEY,
                    database_id INTEGER NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    start_time VARCHAR,
                    end_time VARCHAR,
                    duration_seconds INTEGER,
                    trace_id VARCHAR(255),
                    model_name VARCHAR(255),
                    token_usage_json VARCHAR,
                    context_source VARCHAR(32),
                    used_context INTEGER,
                    fallback_reason VARCHAR,
                    error_message VARCHAR,
                    triggered_by VARCHAR(255),
                    created_at VARCHAR,
                    updated_at VARCHAR
                )
                """
            )
        )
        conn.execute(text("CREATE INDEX ix_pipeline_executions_database_id ON pipeline_executions (database_id)"))

        report = schema_audit.audit_schema(conn)

    table_report = next(item for item in report.table_reports if item.table_name == "pipeline_executions")
    assert "pipeline_context_json" in table_report.missing_columns
    assert table_report.missing_indexes
    assert any("status" in item for item in table_report.missing_indexes)


def test_readiness_snapshots_schema_drift_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    metadata = MetaData()
    Table(
        "readiness_snapshots",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("database_id", Integer, nullable=False),
        Column("readiness_status", String(32), nullable=False),
        Column("generated_at", String),
        Column("ai_summary", String),
        Column("prompt_id", String(255)),
        Column("prompt_version", String(64)),
        Column("model_name", String(255)),
        Index("ix_readiness_snapshots_database_id", "database_id"),
        Index("ix_readiness_snapshots_readiness_status", "readiness_status"),
        Index("ix_readiness_snapshots_generated_at", "generated_at"),
    )

    monkeypatch.setattr(schema_audit, "Base", SimpleNamespace(metadata=metadata))

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE readiness_snapshots (
                    id INTEGER PRIMARY KEY,
                    database_id INTEGER NOT NULL,
                    readiness_status VARCHAR(32) NOT NULL,
                    ai_summary VARCHAR,
                    prompt_id VARCHAR(255),
                    prompt_version VARCHAR(64),
                    model_name VARCHAR(255)
                )
                """
            )
        )
        conn.execute(text("CREATE INDEX ix_readiness_snapshots_database_id ON readiness_snapshots (database_id)"))
        conn.execute(text("CREATE INDEX ix_readiness_snapshots_readiness_status ON readiness_snapshots (readiness_status)"))

        report = schema_audit.audit_schema(conn)

    table_report = next(item for item in report.table_reports if item.table_name == "readiness_snapshots")
    assert "generated_at" in table_report.missing_columns
    assert table_report.missing_indexes
    assert any("generated_at" in item for item in table_report.missing_indexes)
