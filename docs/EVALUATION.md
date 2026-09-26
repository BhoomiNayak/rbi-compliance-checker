# Evaluation & Data Methodology

This document explains how detection quality is measured and — just as important —
the limitations of that measurement. It is written to be read by a skeptical
reviewer.

## Honest framing

This is a **prototype with a rigorous-but-synthetic evaluation**, not a
production-validated system. There is no real debt-collection call data here, and
there shouldn't be: real transcripts contain borrower PII governed by RBI / DPDP
rules and are confidential to the institutions that hold them. So the corpus is
**synthetic and deliberately adversarial**. Its value is that the hard cases are
genuinely hard, not that they are real.

## How the corpus was built (hybrid, option C)

The labeled set (`eval/labeled_set.jsonl`, 33 calls) mixes three sources:

| Source | Count | How created | Why |
| --- | --- | --- | --- |
| Original demo samples | 5 | Hand-authored | Overt violations + one clean call |
| Hand-crafted hard cases | 14 | Hand-authored, grounded in RBI Fair Practices language | The cases that actually test the system |
| LLM-generated filler | 14 | Generated from fixed scenario specs, then labeled from the **spec** (not the model) | Volume for meaningful rates |

The 14 hand-crafted hard cases break down as:
- **5 false-positive cases** (`FP_*`): firm-but-legal calls — legal-notice
  explanations, dispute handling, lawful mention of CIBIL/late fees. These MUST
  score COMPLIANT. Over-flagging is the expensive error in compliance.
- **5 subtle-threat cases** (`ADV_*`): implied/coded coercion, not the obvious
  "police leke aaunga" — office shaming, family pressure, "I'm not threatening
  you but..." framing, veiled references to a borrower's child. These test whether
  the model reads intent, not keywords.
- **4 edge cases** (`EDGE_*`): timing exactly on the 19:00 boundary vs 19:01,
  consent given late, exactly at the call cap.

### Avoiding circular evaluation
The LLM-generated filler is labeled from its **generation spec**, never by asking
the model to grade itself. Generation and labeling are separate steps.

## Metrics reported (`python eval/run_eval.py`)

- **Compliance-status accuracy** — did the call land in the right bucket.
- **Call-level confusion matrix** — flagged vs truly-violating, with call
  precision/recall. Recall matters (don't miss real violations); precision matters
  (don't cry wolf).
- **False-positive rate on the compliant subset** — the over-flagging cost,
  reported explicitly.
- **Per-category P/R/F1** and **per-kind status accuracy**.

## Current results (live model, 33 calls)

> Numbers vary slightly run-to-run because the model is stochastic. Representative:

- Compliance-status accuracy: **32/33 (97%)**
- Call-level: **precision 0.92, recall 1.00** (caught every truly-bad call; zero
  false negatives)
- False-positive rate on compliant calls: **~5% (1/22)**
- Category micro-avg: **P ≈ 0.83, R ≈ 0.79, F1 ≈ 0.81**
- Per-category: time-of-day F1 = 1.00 (deterministic), threat ≈ 0.80,
  harassment ≈ 0.75, consent ≈ 0.67

## Known failure modes (surfaced by the eval, not hidden)

1. **Subtle threat vs harassment confusion.** Two coded-coercion calls
   (`ADV_9202` office-shaming, `ADV_9203` family-pressure) were flagged as
   harassment rather than threat. The model detects wrongdoing but miscategorizes
   the *type* of coercion.
2. **Late-consent over-flag.** `EDGE_9303` (agent gives the recording disclosure a
   few seconds late, after a prompt) is flagged for missing consent — arguably
   too strict.
3. **Occasional consent miss** on a call with many simultaneous violations
   (`EDGE_9304`).

These are exactly the ambiguity cases a production system would need human review
for, which motivates the `REVIEW` status and a human-in-the-loop queue.

## What would make this production-grade

- A larger corpus (hundreds of calls) with **independent human labeling** and
  inter-annotator agreement.
- Real (consented, anonymised) call data under a data-processing agreement.
- Per-category thresholds tuned against a held-out set, plus regression tracking
  of metrics over time.
- Calibrated confidence (the model currently reports ~0.99 on most findings, so
  confidence is not yet a useful triage signal).
