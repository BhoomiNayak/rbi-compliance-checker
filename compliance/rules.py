"""Rulebook loader and deterministic compliance checks.

Only objective, fact-based rules live here: time-of-day and call-frequency cap.
Language judgment (threats, consent, tone) is handled by the LLM analyzer, not
this module. Keeping these deterministic makes them reproducible and defensible
in an audit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from functools import lru_cache
from pathlib import Path

import yaml

from .config import get_config
from .models import Severity, Transcript, Violation, ViolationSource


@dataclass
class Rulebook:
    """Parsed, validated rulebook."""

    hours_start: time
    hours_end: time
    max_calls_per_day: int
    consent_phrases: list[str]
    threat_lexicon: dict[str, list[str]]
    severity_weights: dict[str, int]
    non_compliant_score: int
    review_score: int
    clauses: dict[str, str] = field(default_factory=dict)

    def clause(self, key: str) -> str:
        return self.clauses.get(key, "RBI clause (unspecified — verify)")


def _parse_hhmm(value: str) -> time:
    hh, mm = str(value).strip().split(":")
    return time(hour=int(hh), minute=int(mm))


def load_rulebook(path: str | Path | None = None) -> Rulebook:
    """Load and validate the YAML rulebook."""
    path = Path(path) if path else get_config().rulebook_path
    if not path.exists():
        raise FileNotFoundError(f"Rulebook not found at {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    hours = data.get("hours", {})
    harassment = data.get("harassment", {})
    consent = data.get("consent", {})
    threats = data.get("threats", {})
    weights = data.get("severity_weights", {})
    thresholds = data.get("thresholds", {})

    return Rulebook(
        hours_start=_parse_hhmm(hours.get("start", "08:00")),
        hours_end=_parse_hhmm(hours.get("end", "19:00")),
        max_calls_per_day=int(harassment.get("max_calls_per_day", 2)),
        consent_phrases=[p.lower() for p in consent.get("phrases", [])],
        threat_lexicon={
            "english": list(threats.get("lexicon", {}).get("english", [])),
            "hinglish": list(threats.get("lexicon", {}).get("hinglish", [])),
        },
        severity_weights={
            "CRITICAL": int(weights.get("CRITICAL", 40)),
            "WARNING": int(weights.get("WARNING", 20)),
            "INFO": int(weights.get("INFO", 5)),
        },
        non_compliant_score=int(thresholds.get("non_compliant_score", 40)),
        review_score=int(thresholds.get("review_score", 10)),
        clauses=dict(data.get("clauses", {})),
    )


@lru_cache(maxsize=1)
def get_rulebook() -> Rulebook:
    """Cached rulebook accessor."""
    return load_rulebook()


def reset_rulebook_cache() -> None:
    get_rulebook.cache_clear()


# --------------------------------------------------------------------------- #
# Deterministic checks
# --------------------------------------------------------------------------- #

def check_time_of_day(transcript: Transcript, rb: Rulebook) -> Violation | None:
    """Flag calls started outside the permissible window."""
    if transcript.timestamp is None:
        return None
    call_time = transcript.timestamp.time()
    if rb.hours_start <= call_time <= rb.hours_end:
        return None
    return Violation(
        type="Time-of-Day Violation",
        severity=Severity.WARNING,
        timestamp_offset="00:00",
        quote=(
            f"Call initiated at {call_time.strftime('%H:%M')} "
            f"(permitted {rb.hours_start.strftime('%H:%M')}–"
            f"{rb.hours_end.strftime('%H:%M')})"
        ),
        rbi_clause=rb.clause("time_of_day"),
        source=ViolationSource.DETERMINISTIC,
    )


def check_call_cap(transcript: Transcript, rb: Rulebook) -> Violation | None:
    """Flag borrowers contacted more times today than the cap allows."""
    if transcript.call_count_today <= rb.max_calls_per_day:
        return None
    return Violation(
        type="Re-Contact / Harassment Limit",
        severity=Severity.CRITICAL,
        timestamp_offset="00:00",
        quote=(
            f"{transcript.call_count_today} calls today to this borrower "
            f"(max {rb.max_calls_per_day})"
        ),
        rbi_clause=rb.clause("harassment"),
        source=ViolationSource.DETERMINISTIC,
    )


def run_deterministic_checks(
    transcript: Transcript, rb: Rulebook | None = None
) -> list[Violation]:
    """Run all deterministic checks and return the violations found."""
    rb = rb or get_rulebook()
    violations: list[Violation] = []
    for check in (check_time_of_day, check_call_cap):
        result = check(transcript, rb)
        if result is not None:
            violations.append(result)
    return violations


def is_time_of_day_compliant(transcript: Transcript, rb: Rulebook | None = None) -> bool:
    rb = rb or get_rulebook()
    return check_time_of_day(transcript, rb) is None


# --------------------------------------------------------------------------- #
# CLI: python -m compliance.rules data/samples
# --------------------------------------------------------------------------- #

def _cli(argv: list[str] | None = None) -> int:
    import sys

    from .ingestion import load_directory, load_txt
    from .scoring import score_report

    args = argv if argv is not None else sys.argv[1:]
    target = Path(args[0]) if args else Path("data/samples")
    rb = get_rulebook()

    if target.is_dir():
        transcripts = load_directory(target)
    else:
        transcripts = [load_txt(target)]

    if not transcripts:
        print(f"No transcripts found at {target}")
        return 1

    for t in transcripts:
        violations = run_deterministic_checks(t, rb)
        report = score_report(t, violations, rb)
        print(f"\n=== {report.call_id}  (agent {report.agent_id}) ===")
        print(f"  status: {report.compliance_status.value}")
        print(f"  risk score: {report.overall_risk_score}")
        print(f"  time-of-day compliant: {report.time_of_day_compliant}")
        if report.violations:
            for v in report.violations:
                print(f"  - [{v.severity.value}] {v.type}: {v.quote}")
        else:
            print("  - no deterministic violations")
    print("\n(Note: threat/consent/tone detection requires the LLM layer.)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
