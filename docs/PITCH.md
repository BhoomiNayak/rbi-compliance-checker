# The Craft AI Pitch Narrative

## One-liner

To understand Craft AI's compliance problem, I built a prototype auditor for
collection conversations: it detects RBI recovery-agent violations (including
subtle Hinglish coercion), emits validated compliance telemetry, and generates
audit reports. It's a prototype, not a product — and I can tell you exactly where
it holds up and where it breaks.

## How to pitch it (framing matters)

Say "I built a **prototype to explore this problem**, and here's what I learned
about the hard parts" — NOT "here's a finished solution for your product." The
honest framing is stronger: it invites a conversation about the real engineering
challenges instead of an audit of an overclaim. The project's credibility comes
from the evaluation and the honesty about limitations, not from pretending it's
production-ready.

## Why it maps to Craft AI

Craft AI is an Agentic AI OS for lending. Its Collections module deploys
conversational Voice AI agents for EMI reminders, promise-to-pay tracking, and
recovery calls, and it advertises RBI adherence with timestamped audit logs.

Every automated collection call creates regulatory exposure: wrong hour, missing
consent disclosure, a coercive Hinglish phrase, one call too many in a day. Craft
AI needs a system that continuously proves its agents stay inside RBI boundaries.
That is exactly what this project does.

## What it demonstrates about me as a hire

- **Domain seriousness.** I treated RBI rules as auditable configuration and
  refused to hardcode fabricated clause numbers — I flagged the accuracy risk and
  built a reviewable rulebook instead.
- **Engineering judgment.** I split the problem: deterministic Python for
  objective facts (call hours, call caps) and the LLM only for language judgment
  (Hinglish threats, consent, tone). This is cheaper, more accurate, and
  defensible in an audit.
- **Structured, production-minded GenAI.** Native structured output + Pydantic
  validation + one-retry + optional model escalation + provider abstraction.
- **Quality is measured honestly.** A 33-call adversarial eval reports a
  confusion matrix, a false-positive rate, and per-category precision/recall — and
  I document the failure modes rather than hide them. In compliance, over-flagging
  a good agent is the expensive error, so I built a false-positive suite
  specifically to guard it (~5% FP rate, call-level recall 1.00).
- **Bilingual reality, including the subtle cases.** The detector is tested on
  *coded* Hinglish coercion — office shaming, family pressure, "I'm not
  threatening you but..." — not just obvious keyword threats.
- **I know what I didn't solve.** It's batch/offline, the corpus is synthetic, and
  confidence isn't yet calibrated. Naming these is the point.

## Demo script (3 minutes)

1. Upload a batch of sample transcripts (`.zip`).
2. Show the dashboard: portfolio compliance rate, violation distribution, agent
   risk rankings.
3. Open a non-compliant call in the deep-dive: highlighted Hinglish threat card
   with verbatim quote, timestamp, severity, and RBI reference.
4. Show a call flagged purely by deterministic checks (after 7 PM) — no LLM
   needed, proving the hybrid design.
5. Show a **subtly-coded threat** (an `ADV_*` call) being caught — this is the
   hard case that keyword matching would miss.
6. Export the PDF audit certificate.
7. Run `eval/run_eval.py` to show the confusion matrix, false-positive rate, and
   the failure cases you're transparent about.

## If a sharp interviewer pushes back

- *"Is this real data?"* — No, and it shouldn't be; real collection transcripts
  are confidential borrower PII. The corpus is synthetic and adversarial by
  design. See docs/EVALUATION.md.
- *"33 calls is small."* — Agreed. It's enough to expose real failure modes, not
  enough to certify production quality. The path to that (independent human
  labeling, hundreds of calls, held-out tuning) is documented.
- *"This isn't real-time voice like our product."* — Correct. This is the batch
  QA/audit layer; real-time in-call guardrails are a different, harder problem I'd
  scope separately.

## Talking points if asked "what would you do next in production?"

- Ingest directly from Craft AI's call/transcript event stream instead of files.
- Real-time in-call guardrails (block a coercive phrase before it is spoken).
- Human-in-the-loop review queue for `REVIEW`-status calls.
- Versioned rulebook with approval workflow and clause verification against the
  official RBI text.
- Regional language expansion (Tamil, Telugu, Marathi, Bengali code-switching).
- Local Indian data hosting to match Craft AI's data-residency posture.
