"""Pipeline orchestration.

Ties the layers together for a single transcript or a batch:

    ingest -> deterministic checks -> (optional) LLM analysis -> merge -> score

Design notes:
- Works with no API key: deterministic checks still run; LLM findings are skipped
  and the report is annotated so the UI can show a "deterministic-only" badge.
- Batch runs are resilient: one transcript failing does not abort the rest.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .analyzer import analyze_transcript
from .config import Config, get_config
from .llm_provider import LLMProvider, get_provider
from .models import (
    CallComplianceReport,
    Severity,
    Transcript,
    Violation,
    ViolationSource,
)
from .rules import Rulebook, get_rulebook, run_deterministic_checks
from .scoring import score_report


@dataclass
class AnalysisResult:
    """A report plus run metadata for the UI."""

    report: CallComplianceReport
    llm_used: bool = False
    error: str | None = None
    notes: list[str] = field(default_factory=list)


def _is_consent_violation(v: Violation) -> bool:
    """True if a violation is about recording/consent disclosure."""
    t = v.type.lower()
    return "consent" in t or "disclosure" in t or "recording" in t


def _dedupe_violations(violations: list[Violation]) -> list[Violation]:
    """Drop near-duplicate violations (same type + offset), keeping the most severe."""
    order = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}
    best: dict[tuple[str, str], Violation] = {}
    for v in violations:
        key = (v.type.strip().lower(), v.timestamp_offset)
        current = best.get(key)
        if current is None or order[v.severity] < order[current.severity]:
            best[key] = v
    # Preserve a stable, readable ordering: severity then offset.
    return sorted(best.values(), key=lambda v: (order[v.severity], v.timestamp_offset))


def analyze_one(
    transcript: Transcript,
    *,
    provider: LLMProvider | None = None,
    rb: Rulebook | None = None,
    config: Config | None = None,
    use_llm: bool | None = None,
) -> AnalysisResult:
    """Analyze a single transcript and return an AnalysisResult.

    ``use_llm`` defaults to whether an API key is configured. Deterministic checks
    always run. LLM failures degrade gracefully to a deterministic-only report.
    """
    rb = rb or get_rulebook()
    config = config or get_config()
    if use_llm is None:
        use_llm = config.llm_enabled

    deterministic = run_deterministic_checks(transcript, rb)
    consent_given = True
    coaching = ""
    llm_used = False
    notes: list[str] = []
    error: str | None = None

    if use_llm:
        try:
            provider = provider or get_provider(config)
            finding = analyze_transcript(transcript, provider=provider, rb=rb)
            consent_given = finding.consent_given
            coaching = finding.agent_coaching_summary
            llm_used = True

            # Consent is modelled ONLY via the consent_given flag to avoid
            # double-counting. Strip any consent/disclosure violation the LLM may
            # have emitted, then synthesize exactly one canonical violation when
            # the flag is false. This keeps the flag authoritative and the
            # violation purely presentational.
            llm_violations = [
                v
                for v in finding.violations
                if not _is_consent_violation(v)
            ]
            if not consent_given:
                llm_violations.append(
                    Violation(
                        type="Missing Recording Consent",
                        severity=Severity.WARNING,
                        timestamp_offset="00:00",
                        quote="No recording/identity disclosure detected in the call opening.",
                        rbi_clause=rb.clause("consent"),
                        source=ViolationSource.LLM,
                    )
                )
        except Exception as exc:  # noqa: BLE001 - degrade gracefully, record why
            error = str(exc)
            notes.append("LLM analysis failed; showing deterministic checks only.")
            llm_violations = []
    else:
        notes.append("No API key: deterministic checks only (time-of-day, call-cap).")
        llm_violations = []

    violations = _dedupe_violations([*deterministic, *llm_violations])
    report = score_report(
        transcript,
        violations,
        rb,
        consent_given=consent_given,
        coaching_summary=coaching,
    )
    return AnalysisResult(report=report, llm_used=llm_used, error=error, notes=notes)


def analyze_batch(
    transcripts: list[Transcript],
    *,
    provider: LLMProvider | None = None,
    rb: Rulebook | None = None,
    config: Config | None = None,
    use_llm: bool | None = None,
    progress=None,
) -> list[AnalysisResult]:
    """Analyze many transcripts. One failure never aborts the batch.

    ``progress`` is an optional callable(done, total) for UI progress bars.
    """
    rb = rb or get_rulebook()
    config = config or get_config()
    if use_llm is None:
        use_llm = config.llm_enabled
    if use_llm and provider is None:
        try:
            provider = get_provider(config)
        except Exception:  # noqa: BLE001 - fall back to deterministic-only
            provider = None
            use_llm = False

    results: list[AnalysisResult] = []
    total = len(transcripts)
    for i, t in enumerate(transcripts, start=1):
        try:
            results.append(
                analyze_one(t, provider=provider, rb=rb, config=config, use_llm=use_llm)
            )
        except Exception as exc:  # noqa: BLE001 - keep going on per-file errors
            fallback = score_report(t, run_deterministic_checks(t, rb), rb)
            results.append(
                AnalysisResult(
                    report=fallback,
                    llm_used=False,
                    error=str(exc),
                    notes=["Unexpected error; deterministic fallback used."],
                )
            )
        if progress:
            progress(i, total)
    return results
