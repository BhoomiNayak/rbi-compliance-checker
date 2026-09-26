"""Generate routine 'filler' transcripts for the eval corpus (option-C hybrid).

The hard adversarial and false-positive cases are hand-authored (grounded in RBI
Fair Practices language). This script only generates the *routine* volume so the
corpus is large enough for meaningful metrics. Each generated call is driven by a
scenario spec so we know its intended label WITHOUT asking the model to label
itself — generation and labeling stay separate (avoids circular evaluation).

Usage:
    python eval/generate_filler.py            # writes .txt files + a labels file
    python eval/generate_filler.py --n 25

Requires GEMINI_API_KEY. Output goes to data/eval_corpus/ and appends to
eval/filler_labels.jsonl.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from compliance.config import get_config  # noqa: E402
from compliance.llm_provider import get_provider  # noqa: E402
from pydantic import BaseModel  # noqa: E402

CORPUS = Path(__file__).resolve().parent.parent / "data" / "eval_corpus"
LABELS = Path(__file__).resolve().parent / "filler_labels.jsonl"

# Scenario specs: (compliant?, in_hours?, within_cap?, consent?, note). The label
# is derived from the SPEC, not from the model output.
SCENARIOS = [
    ("compliant", True, True, True, "polite EMI reminder, promise to pay"),
    ("compliant", True, True, True, "customer already paid, agent confirms"),
    ("compliant", True, True, True, "restructuring offer, empathetic tone"),
    ("compliant", True, True, True, "wrong number, agent apologises and ends"),
    ("compliant", True, True, True, "customer requests callback, agent agrees"),
]


class GeneratedCall(BaseModel):
    transcript: str  # dialogue only, with [mm:ss] Speaker: lines


_PROMPT = """Generate a realistic Indian debt-collection call transcript in \
English or light Hinglish. Format each line as "[mm:ss] Agent:" or \
"[mm:ss] Customer:". 5-8 turns. Scenario: {note}. The agent MUST be fully \
RBI-compliant: state the call is recorded at the start, be polite, no threats, \
no coercion, only factual reminders and lawful consequences. Do NOT include a \
metadata header — dialogue only."""


def _spec_to_expected(spec) -> dict:
    _kind, in_hours, within_cap, consent, _note = spec
    cats = []
    if not in_hours:
        cats.append("time_of_day")
    if not within_cap:
        cats.append("harassment")
    if not consent:
        cats.append("consent")
    status = "COMPLIANT" if not cats else "REVIEW"
    return {"expected_status": status, "expected_categories": cats}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=len(SCENARIOS))
    args = parser.parse_args()

    get_config().require_api_key()
    provider = get_provider()
    CORPUS.mkdir(parents=True, exist_ok=True)

    base_ts = datetime(2026, 9, 22, 10, 0)
    written = []
    for i in range(args.n):
        spec = SCENARIOS[i % len(SCENARIOS)]
        note = spec[4]
        raw = provider.generate_json(_PROMPT.format(note=note), GeneratedCall)
        call = GeneratedCall.model_validate_json(raw)

        cid = f"FILL_{9400 + i}"
        agent = f"AGT_9{i:02d}"
        ts = (base_ts + timedelta(minutes=7 * i)).strftime("%Y-%m-%dT%H:%M:%S")
        header = (
            f"Call_ID: {cid}\nAgent_ID: {agent}\nCustomer_ID: CUST_9{i:03d}\n"
            f"Call_Timestamp: {ts}\nCall_Count_Today: 1\n---\n"
        )
        fname = f"{cid}_{agent}.txt"
        (CORPUS / fname).write_text(header + call.transcript.strip() + "\n", encoding="utf-8")

        label = {"file": fname, **_spec_to_expected(spec)}
        written.append(label)
        # Append incrementally so a timeout/interrupt never loses labels.
        with LABELS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(label) + "\n")
        print(f"wrote {fname}  ({label['expected_status']})")

    print(f"\n{len(written)} filler calls -> {CORPUS}\nlabels appended -> {LABELS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
