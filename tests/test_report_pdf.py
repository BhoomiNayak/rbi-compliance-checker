from datetime import datetime

from compliance.models import (
    CallComplianceReport,
    ComplianceStatus,
    Severity,
    Violation,
    ViolationSource,
)
from compliance.report_pdf import build_batch_pdf, build_call_pdf


def _report():
    return CallComplianceReport(
        call_id="TRANSCRIPT_8902",
        agent_id="AGT_402",
        customer_id="CUST_1",
        timestamp=datetime(2026, 9, 22, 19, 45),
        compliance_status=ComplianceStatus.NON_COMPLIANT,
        overall_risk_score=100,
        time_of_day_compliant=False,
        consent_given=False,
        call_count_today=3,
        violations=[
            Violation(
                type="Illegal Threat Term",
                severity=Severity.CRITICAL,
                timestamp_offset="01:22",
                # includes curly quotes + non-latin to exercise sanitisation
                quote="ghar pe police leke aaunga \u2014 \u201cbeizzati\u201d",
                rbi_clause="RBI Master Direction (verify)",
                source=ViolationSource.LLM,
                confidence=0.99,
            )
        ],
        agent_coaching_summary="Agent used unlawful threats in Hinglish.",
    )


def test_build_call_pdf_returns_bytes():
    data = build_call_pdf(_report())
    assert isinstance(data, (bytes, bytearray))
    assert len(data) > 500
    assert data[:4] == b"%PDF"


def test_build_batch_pdf_returns_bytes():
    reports = [_report(), _report()]
    data = build_batch_pdf(reports)
    assert data[:4] == b"%PDF"
    assert len(data) > 800


def test_pdf_handles_compliant_report():
    clean = CallComplianceReport(call_id="T2", agent_id="A2")
    data = build_call_pdf(clean)
    assert data[:4] == b"%PDF"
