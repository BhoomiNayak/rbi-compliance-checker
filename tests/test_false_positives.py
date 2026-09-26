"""False-positive suite: firm-but-legal calls must NOT be flagged.

Over-flagging (marking a compliant agent as non-compliant) is the expensive error
in a compliance tool, so we guard it explicitly.

- Mocked tests always run and prove the pipeline does not invent violations when
  the LLM reports a clean call, including for in-hours / within-cap / consented
  metadata.
- The live-gated test runs the real model over the hand-crafted false-positive
  corpus and asserts none are marked NON_COMPLIANT (only when GEMINI_API_KEY set).
"""

import json
import os
from datetime import datetime
from pathlib import Path

import pytest

from compliance.ingestion import load_txt
from compliance.models import ComplianceStatus, Transcript
from compliance.pipeline import analyze_one
from compliance.rules import load_rulebook

RB = load_rulebook()
ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "eval_corpus"
LABELS = ROOT / "eval" / "labeled_set.jsonl"

CLEAN_PAYLOAD = {"consent_given": True, "violations": [], "agent_coaching_summary": ""}


class FakeProvider:
    def __init__(self, payload):
        self._payload = payload

    def generate_json(self, prompt, schema, *, model=None):
        return json.dumps(self._payload)


def test_clean_llm_result_yields_no_violations():
    """A compliant, in-hours, within-cap, consented call must be COMPLIANT."""
    t = Transcript(
        call_id="FP", agent_id="A", customer_id="C",
        timestamp=datetime(2026, 9, 22, 11, 0), call_count_today=1,
        text="[00:00] Agent: recorded line, polite reminder.",
    )
    result = analyze_one(t, provider=FakeProvider(CLEAN_PAYLOAD), rb=RB, use_llm=True)
    assert result.report.compliance_status is ComplianceStatus.COMPLIANT
    assert result.report.overall_risk_score == 0
    assert result.report.violations == []


def test_consent_true_does_not_synthesize_violation():
    """When consent_given is True, no consent violation should be added."""
    t = Transcript(
        call_id="FP2", agent_id="A", timestamp=datetime(2026, 9, 22, 11, 0),
        call_count_today=1, text="hi",
    )
    result = analyze_one(t, provider=FakeProvider(CLEAN_PAYLOAD), rb=RB, use_llm=True)
    assert all("consent" not in v.type.lower() for v in result.report.violations)


def _fp_files() -> list[str]:
    rows = [json.loads(l) for l in LABELS.read_text().splitlines() if l.strip()]
    return [r["file"] for r in rows if r.get("kind") == "false_positive"]


@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"), reason="live test requires GEMINI_API_KEY"
)
@pytest.mark.parametrize("fname", _fp_files())
def test_live_false_positives_not_flagged(fname):
    """Real model over firm-but-legal calls: none should be NON_COMPLIANT."""
    result = analyze_one(load_txt(CORPUS / fname), rb=RB, use_llm=True)
    assert result.report.compliance_status is not ComplianceStatus.NON_COMPLIANT, (
        f"{fname} was over-flagged as NON_COMPLIANT: "
        f"{[v.type for v in result.report.violations]}"
    )
