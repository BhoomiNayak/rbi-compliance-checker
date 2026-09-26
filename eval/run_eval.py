"""Evaluation harness: precision / recall of violation-category detection.

Runs the full pipeline over the labeled set and compares detected violation
categories against the gold labels. Categories are canonicalised from violation
types so the metric is robust to the LLM's exact wording.

Usage:
    python eval/run_eval.py                 # uses LLM if GEMINI_API_KEY is set
    python eval/run_eval.py --no-llm        # deterministic-only baseline
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from compliance.ingestion import load_txt  # noqa: E402
from compliance.models import CallComplianceReport  # noqa: E402
from compliance.pipeline import analyze_one  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
DATA_DIR = EVAL_DIR.parent / "data"
LABELS = EVAL_DIR / "labeled_set.jsonl"

CATEGORIES = ["time_of_day", "harassment", "threat", "consent"]


def categorize(report: CallComplianceReport) -> set[str]:
    """Map a report's violations to canonical categories.

    Consent is derived ONLY from the consent_given flag (the single source of
    truth), so consent is never double-attributed from both the flag and a
    violation type.
    """
    cats: set[str] = set()
    for v in report.violations:
        t = v.type.lower()
        if "time-of-day" in t or "timing" in t or "hours" in t:
            cats.add("time_of_day")
        elif "re-contact" in t or "harassment" in t or "frequency" in t:
            cats.add("harassment")
        elif "threat" in t or "coercion" in t or "shaming" in t or "intimidat" in t:
            cats.add("threat")
        # consent handled below via the flag only
    if not report.consent_given:
        cats.add("consent")
    return cats


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def _resolve(row: dict) -> Path:
    """Locate a labeled transcript by its declared source_dir."""
    src = row.get("source_dir", "samples")
    base = DATA_DIR / src
    return base / row["file"]


def run(use_llm: bool | None) -> int:
    labels = [json.loads(line) for line in LABELS.read_text().splitlines() if line.strip()]

    tp = fp = fn = 0
    status_correct = 0
    per_cat = {c: {"tp": 0, "fp": 0, "fn": 0} for c in CATEGORIES}
    per_kind: dict[str, dict[str, int]] = {}

    # Binary call-level confusion matrix: is the call flagged (non-compliant/review)
    # vs truly having any violation? This is what a compliance buyer cares about.
    call_tp = call_fp = call_tn = call_fn = 0
    # False-positive tracking on the truly-compliant subset (over-flagging cost).
    compliant_total = compliant_flagged = 0

    print(f"\nEvaluating {len(labels)} labeled calls (use_llm={use_llm})\n")
    print(f"{'call':<22}{'kind':<15}{'status':<8}{'P':>5}{'R':>6}  detail")
    print("-" * 84)

    for row in labels:
        transcript = load_txt(_resolve(row))
        result = analyze_one(transcript, use_llm=use_llm)
        detected = categorize(result.report)
        expected = set(row["expected_categories"])
        kind = row.get("kind", "unknown")

        row_tp = len(detected & expected)
        row_fp = len(detected - expected)
        row_fn = len(expected - detected)
        tp, fp, fn = tp + row_tp, fp + row_fp, fn + row_fn

        for c in CATEGORIES:
            if c in detected and c in expected:
                per_cat[c]["tp"] += 1
            elif c in detected and c not in expected:
                per_cat[c]["fp"] += 1
            elif c not in detected and c in expected:
                per_cat[c]["fn"] += 1

        # Call-level binary (any violation expected vs any detected).
        exp_any = bool(expected)
        det_any = bool(detected)
        if exp_any and det_any:
            call_tp += 1
        elif not exp_any and det_any:
            call_fp += 1
        elif not exp_any and not det_any:
            call_tn += 1
        else:
            call_fn += 1

        if not exp_any:
            compliant_total += 1
            if det_any:
                compliant_flagged += 1

        pk = per_kind.setdefault(kind, {"n": 0, "status_ok": 0})
        pk["n"] += 1

        status_ok = result.report.compliance_status.value == row["expected_status"]
        status_correct += int(status_ok)
        pk["status_ok"] += int(status_ok)

        p, r, _ = _prf(row_tp, row_fp, row_fn)
        missing = expected - detected
        extra = detected - expected
        detail = []
        if missing:
            detail.append(f"missed={sorted(missing)}")
        if extra:
            detail.append(f"OVER-FLAG={sorted(extra)}")
        print(
            f"{row['file'][:22]:<22}{kind:<15}{'ok' if status_ok else 'MISS':<8}"
            f"{p:>5.2f}{r:>6.2f}  {'; '.join(detail)}"
        )

    print("-" * 84)
    p, r, f1 = _prf(tp, fp, fn)
    print("\nViolation-category detection (micro-averaged):")
    print(f"  precision = {p:.3f}   recall = {r:.3f}   F1 = {f1:.3f}")

    print("\nCall-level confusion matrix (flagged vs truly-violating):")
    print(f"                 predicted+   predicted-")
    print(f"  actual+ (bad)  TP={call_tp:<9} FN={call_fn}")
    print(f"  actual- (ok)   FP={call_fp:<9} TN={call_tn}")
    cp, cr, cf = _prf(call_tp, call_fp, call_fn)
    print(f"  call precision = {cp:.3f}   call recall = {cr:.3f}   F1 = {cf:.3f}")

    fpr = (compliant_flagged / compliant_total) if compliant_total else 0.0
    print(
        f"\nFalse-positive rate on compliant calls: "
        f"{compliant_flagged}/{compliant_total} ({100 * fpr:.0f}%)  "
        f"[lower is better — over-flagging is the expensive error]"
    )

    print(f"\nCompliance-status accuracy = {status_correct}/{len(labels)} "
          f"({100 * status_correct / len(labels):.0f}%)")

    print("\nPer-category (P / R / F1):")
    for c in CATEGORIES:
        cpp, crr, cff = _prf(per_cat[c]["tp"], per_cat[c]["fp"], per_cat[c]["fn"])
        print(f"  {c:<12} P={cpp:.2f} R={crr:.2f} F1={cff:.2f}")

    print("\nStatus accuracy by case kind:")
    for kind, d in sorted(per_kind.items()):
        print(f"  {kind:<16} {d['status_ok']}/{d['n']}")
    print()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-llm", action="store_true", help="deterministic-only baseline")
    args = parser.parse_args()
    return run(use_llm=False if args.no_llm else None)


if __name__ == "__main__":
    raise SystemExit(main())
