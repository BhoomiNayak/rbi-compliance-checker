import json
from datetime import datetime

from compliance.models import ComplianceStatus, Severity, Transcript
from compliance.pipeline import analyze_batch, analyze_one
from compliance.rules import load_rulebook

RB = load_rulebook()


class FakeProvider:
    def __init__(self, payload):
        self._payload = payload

    def generate_json(self, prompt, schema, *, model=None):
        return json.dumps(self._payload)


class BoomProvider:
    def generate_json(self, prompt, schema, *, model=None):
        raise RuntimeError("api exploded")


THREAT_PAYLOAD = {
    "consent_given": False,
    "violations": [
        {
            "type": "Illegal Threat Term",
            "severity": "CRITICAL",
            "timestamp_offset": "01:22",
            "quote": "police leke aaunga",
            "rbi_clause": "",
            "source": "llm",
            "confidence": 0.97,
        }
    ],
    "agent_coaching_summary": "Threatened police action.",
}

CLEAN_PAYLOAD = {"consent_given": True, "violations": [], "agent_coaching_summary": ""}


def _t(**kw):
    base = dict(call_id="C", agent_id="A", customer_id="CU", text="[00:00] hi")
    base.update(kw)
    return Transcript(**base)


def test_no_llm_runs_deterministic_only():
    t = _t(timestamp=datetime(2026, 9, 22, 19, 45), call_count_today=3)
    result = analyze_one(t, rb=RB, use_llm=False)
    assert result.llm_used is False
    assert result.report.compliance_status is ComplianceStatus.NON_COMPLIANT
    # both deterministic violations present, no LLM ones
    types = {v.type for v in result.report.violations}
    assert "Time-of-Day Violation" in types
    assert "Re-Contact / Harassment Limit" in types


def test_llm_and_deterministic_merge():
    t = _t(timestamp=datetime(2026, 9, 22, 19, 45), call_count_today=1)
    result = analyze_one(t, provider=FakeProvider(THREAT_PAYLOAD), rb=RB, use_llm=True)
    assert result.llm_used is True
    types = [v.type for v in result.report.violations]
    assert "Time-of-Day Violation" in types  # deterministic
    assert "Illegal Threat Term" in types     # llm
    # consent False -> synthesized missing-consent violation added
    assert any("Consent" in v.type for v in result.report.violations)
    assert result.report.compliance_status is ComplianceStatus.NON_COMPLIANT


def test_clean_call_is_compliant():
    t = _t(timestamp=datetime(2026, 9, 22, 11, 0), call_count_today=1)
    result = analyze_one(t, provider=FakeProvider(CLEAN_PAYLOAD), rb=RB, use_llm=True)
    assert result.report.compliance_status is ComplianceStatus.COMPLIANT
    assert result.report.overall_risk_score == 0


def test_llm_failure_degrades_gracefully():
    t = _t(timestamp=datetime(2026, 9, 22, 11, 0), call_count_today=1)
    result = analyze_one(t, provider=BoomProvider(), rb=RB, use_llm=True)
    assert result.llm_used is False
    assert result.error is not None
    assert "deterministic" in " ".join(result.notes).lower()


def test_batch_resilient_and_complete():
    ts = [
        _t(call_id="A1", timestamp=datetime(2026, 9, 22, 11, 0), call_count_today=1),
        _t(call_id="A2", timestamp=datetime(2026, 9, 22, 19, 45), call_count_today=3),
    ]
    results = analyze_batch(ts, provider=FakeProvider(CLEAN_PAYLOAD), rb=RB, use_llm=True)
    assert len(results) == 2
    by_id = {r.report.call_id: r for r in results}
    assert by_id["A1"].report.compliance_status is ComplianceStatus.COMPLIANT
    assert by_id["A2"].report.compliance_status is ComplianceStatus.NON_COMPLIANT


def test_empty_batch_returns_empty():
    assert analyze_batch([], rb=RB, use_llm=False) == []


def test_duplicate_call_ids_stay_distinct():
    """Two calls sharing a call_id must yield two separate results (the deep-dive
    keys transcript text by index, not call_id, to avoid collisions)."""
    ts = [
        _t(call_id="DUP", agent_id="A1", text="first", timestamp=datetime(2026, 9, 22, 11, 0)),
        _t(call_id="DUP", agent_id="A2", text="second", timestamp=datetime(2026, 9, 22, 19, 45), call_count_today=3),
    ]
    results = analyze_batch(ts, provider=FakeProvider(CLEAN_PAYLOAD), rb=RB, use_llm=True)
    assert len(results) == 2
    assert results[0].report.agent_id == "A1"
    assert results[1].report.agent_id == "A2"
    # distinct compliance outcomes preserved
    assert results[0].report.compliance_status is ComplianceStatus.COMPLIANT
    assert results[1].report.compliance_status is ComplianceStatus.NON_COMPLIANT
