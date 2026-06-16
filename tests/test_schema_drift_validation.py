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

    def has_critical_errors(self) -> bool:
        return self.has_errors

    def has_warnings(self) -> bool:
        return bool(self.requires_manual_review)


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


def test_validate_schema_drift_warns_but_does_not_raise_on_noncritical_drift(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.db.init_db.audit_schema",
        lambda _: _ReportStub(requires_manual_review=["table_x: extra columns foo"], has_errors=False),
    )
    _validate_schema_drift(object())


def test_validate_schema_drift_can_bypass_critical_errors_when_not_strict(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.db.init_db.audit_schema",
        lambda _: _ReportStub(has_errors=True),
    )
    monkeypatch.setattr("app.db.init_db.settings", type("S", (), {"strict_schema_validation": False})())
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


def test_schema_audit_severity_methods_separate_errors_and_warnings():
    critical = SchemaAuditTableReport(
        table_name="schema_relationship_graph",
        missing_columns=["estimated_tokens"],
        type_mismatches=["cluster_summary (Text != String)"],
    )
    warning = SchemaAuditTableReport(
        table_name="governance_packages",
        extra_columns=["legacy_field"],
        missing_indexes=["ix_governance_packages_database_id"],
        duplicate_indexes=["database_id"],
    )
    report = SchemaAuditReport(table_reports=[critical, warning])

    assert report.has_critical_errors()
    assert report.has_warnings()
    assert critical.has_critical_errors()
    assert not critical.has_warnings()
    assert not warning.has_critical_errors()
    assert warning.has_warnings()
