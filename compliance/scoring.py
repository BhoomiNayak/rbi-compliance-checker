"""Deterministic risk scoring and status classification.

The score is computed in Python from the set of detected violations (both
deterministic and LLM-sourced) so the final number is reproducible and auditable
regardless of the LLM's stochasticity.
"""

from __future__ import annotations

from .models import (
    CallComplianceReport,
    ComplianceStatus,
    Severity,
    Transcript,
    Violation,
)
from .rules import Rulebook, get_rulebook, is_time_of_day_compliant


def compute_risk_score(violations: list[Violation], rb: Rulebook) -> int:
    """Sum severity weights, capped at 100."""
    total = 0
    for v in violations:
        total += rb.severity_weights.get(v.severity.value, 0)
    return min(total, 100)


def classify_status(
    violations: list[Violation], score: int, rb: Rulebook
) -> ComplianceStatus:
    """Map violations + score to an overall status."""
    has_critical = any(v.severity is Severity.CRITICAL for v in violations)
    if has_critical or score >= rb.non_compliant_score:
        return ComplianceStatus.NON_COMPLIANT
    if score >= rb.review_score or violations:
        return ComplianceStatus.REVIEW
    return ComplianceStatus.COMPLIANT


def score_report(
    transcript: Transcript,
    violations: list[Violation],
    rb: Rulebook | None = None,
    *,
    consent_given: bool = True,
    coaching_summary: str = "",
) -> CallComplianceReport:
    """Build a fully validated CallComplianceReport from a transcript + violations."""
    rb = rb or get_rulebook()
    score = compute_risk_score(violations, rb)
    status = classify_status(violations, score, rb)

    return CallComplianceReport(
        call_id=transcript.call_id,
        agent_id=transcript.agent_id,
        customer_id=transcript.customer_id,
        timestamp=transcript.timestamp,
        compliance_status=status,
        overall_risk_score=score,
        time_of_day_compliant=is_time_of_day_compliant(transcript, rb),
        consent_given=consent_given,
        call_count_today=transcript.call_count_today,
        violations=violations,
        agent_coaching_summary=coaching_summary,
    )
