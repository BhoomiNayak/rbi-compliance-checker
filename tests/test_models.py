import pytest
from pydantic import ValidationError

from compliance.models import (
    CallComplianceReport,
    ComplianceStatus,
    Severity,
    Transcript,
    Violation,
    ViolationSource,
)


def test_violation_valid_build():
    v = Violation(
        type="Illegal Threat Term",
        severity=Severity.CRITICAL,
        timestamp_offset="01:22",
        quote="police leke aaunga",
        rbi_clause="cl. X",
        source=ViolationSource.LLM,
        confidence=0.9,
    )
    assert v.severity is Severity.CRITICAL
    assert v.source is ViolationSource.LLM


def test_violation_confidence_out_of_range_rejected():
    with pytest.raises(ValidationError):
        Violation(
            type="X", severity=Severity.INFO, quote="q", rbi_clause="c", confidence=1.5
        )


def test_report_score_bounds_enforced():
    with pytest.raises(ValidationError):
        CallComplianceReport(call_id="c", agent_id="a", overall_risk_score=150)


def test_report_json_round_trip():
    report = CallComplianceReport(
        call_id="TRANSCRIPT_1",
        agent_id="AGT_1",
        compliance_status=ComplianceStatus.NON_COMPLIANT,
        overall_risk_score=85,
    )
    dumped = report.model_dump_json()
    restored = CallComplianceReport.model_validate_json(dumped)
    assert restored.overall_risk_score == 85
    assert restored.compliance_status is ComplianceStatus.NON_COMPLIANT


def test_transcript_negative_call_count_rejected():
    with pytest.raises(ValidationError):
        Transcript(call_id="c", agent_id="a", call_count_today=-1)
