from datetime import datetime

import pytest

from compliance.models import Severity, Transcript, Violation, ViolationSource
from compliance.rules import (
    check_call_cap,
    check_time_of_day,
    load_rulebook,
    run_deterministic_checks,
)
from compliance.scoring import classify_status, compute_risk_score, score_report
from compliance.models import ComplianceStatus


@pytest.fixture(scope="module")
def rb():
    return load_rulebook()


def _t(**kw):
    base = dict(call_id="C", agent_id="A", customer_id="CU")
    base.update(kw)
    return Transcript(**base)


def test_time_of_day_flagged_after_hours(rb):
    t = _t(timestamp=datetime(2026, 9, 22, 19, 45))
    v = check_time_of_day(t, rb)
    assert v is not None
    assert v.severity is Severity.WARNING
    assert v.source is ViolationSource.DETERMINISTIC


def test_time_of_day_ok_within_hours(rb):
    t = _t(timestamp=datetime(2026, 9, 22, 11, 10))
    assert check_time_of_day(t, rb) is None


def test_time_of_day_none_when_no_timestamp(rb):
    assert check_time_of_day(_t(), rb) is None


def test_call_cap_flagged_over_limit(rb):
    v = check_call_cap(_t(call_count_today=3), rb)
    assert v is not None
    assert v.severity is Severity.CRITICAL


def test_call_cap_ok_within_limit(rb):
    assert check_call_cap(_t(call_count_today=2), rb) is None


def test_score_capped_at_100(rb):
    vs = [
        Violation(type="x", severity=Severity.CRITICAL, quote="q", rbi_clause="c")
        for _ in range(5)
    ]
    assert compute_risk_score(vs, rb) == 100


def test_status_clean_is_compliant(rb):
    assert classify_status([], 0, rb) is ComplianceStatus.COMPLIANT


def test_status_critical_is_non_compliant(rb):
    vs = [Violation(type="x", severity=Severity.CRITICAL, quote="q", rbi_clause="c")]
    score = compute_risk_score(vs, rb)
    assert classify_status(vs, score, rb) is ComplianceStatus.NON_COMPLIANT


def test_end_to_end_clean_call(rb):
    t = _t(timestamp=datetime(2026, 9, 22, 11, 10), call_count_today=1)
    report = score_report(t, run_deterministic_checks(t, rb), rb)
    assert report.overall_risk_score == 0
    assert report.compliance_status is ComplianceStatus.COMPLIANT
    assert report.time_of_day_compliant is True


def test_end_to_end_bad_call(rb):
    t = _t(timestamp=datetime(2026, 9, 22, 19, 45), call_count_today=3)
    violations = run_deterministic_checks(t, rb)
    report = score_report(t, violations, rb)
    assert len(violations) == 2  # time-of-day + call-cap
    assert report.compliance_status is ComplianceStatus.NON_COMPLIANT
    assert report.time_of_day_compliant is False
    assert report.overall_risk_score >= 40
