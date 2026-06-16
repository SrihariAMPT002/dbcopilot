from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.db.init_db import _validate_schema_drift
from app.db.schema_audit import SchemaAuditReport, SchemaAuditTableReport


@dataclass
class _ReportStub:
    requires_manual_review: list[str] = field(default_factory=list)
    has_errors: bool = False

    def format_message(self) -> str:
        return "Schema drift detected: stub"


def test_validate_schema_drift_passes_when_audit_is_clean(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.db.init_db.audit_schema", lambda _: _ReportStub())
    _validate_schema_drift(object())


def test_validate_schema_drift_raises_on_errors(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.db.init_db.audit_schema",
        lambda _: _ReportStub(has_errors=True),
    )
    with pytest.raises(RuntimeError, match="Schema drift detected"):
        _validate_schema_drift(object())


def test_schema_audit_report_formats_table_issues():
    report = SchemaAuditReport(
        table_reports=[
            SchemaAuditTableReport(
                table_name="kpi_intelligence",
                missing_columns=["estimated_tokens", "retry_count"],
                extra_columns=["legacy_field"],
                missing_indexes=["ix_kpi_intelligence_cluster_id"],
            )
        ]
    )
    message = report.format_message()
    assert "kpi_intelligence" in message
    assert "missing columns estimated_tokens, retry_count" in message
    assert "extra columns legacy_field" in message
    assert "missing indexes ix_kpi_intelligence_cluster_id" in message
