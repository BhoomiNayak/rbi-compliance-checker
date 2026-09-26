# Implementation Plan — RBI Compliance & Call Quality Inspector

## Problem statement

Build a compliance audit dashboard that scans debt-collection call transcripts,
detects RBI recovery-agent regulatory violations (including Hinglish /
code-switched threats), scores each call deterministically into a validated
schema, and produces an executive dashboard plus exportable PDF audit reports.
Deliverable: a locally runnable Streamlit app, buildable in a day, framed as a
pitch project for a role at Craft AI.

## Requirements

- Batch ingest `.txt` transcripts and `.zip` archives, with call metadata
  (timestamp, customer/agent IDs, calls-today count).
- Multi-tier rules engine:
  - Time-of-day (deterministic; 8:00 AM - 7:00 PM per RBI Fair Practices norms,
    configurable).
  - Recording-consent disclosure check (LLM-assisted).
  - Hinglish/English threat & coercion detection (LLM; police/jail/arrest/court/
    home-visit/beizzati, etc.).
  - Re-contact / harassment cap (deterministic; > 2 calls/day, configurable) plus
    tone escalation (LLM).
- Deterministic risk scoring 0-100 with severity `CRITICAL / WARNING / INFO`.
- Pydantic-validated structured output; each violation maps to timestamp offset,
  verbatim quote, severity, and an RBI clause reference from a configurable
  rulebook.
- Executive dashboard (portfolio compliance rate, violation distribution, agent
  risk rankings) plus split-screen transcript deep-dive with highlighted
  violation cards.
- One-click PDF audit report export.
- Runnable locally and on Streamlit Cloud, free-tier friendly.

## Technical decisions

- **LLM:** Google Gemini via `google-genai`. Primary `gemini-flash-latest`;
  optional escalation to `gemini-pro-latest` for high-severity / low-confidence
  calls; automatic fallback through `gemini-flash-lite-latest` /
  `gemini-3-flash-preview` on transient 503 spikes. Model IDs live in config for
  easy swapping. (Pinned version IDs like `gemini-2.5-flash` are rejected for
  newly created API keys, so we use the `-latest` aliases.)
- **Structured output:** Gemini native structured output driven by
  `PydanticModel.model_json_schema()`, then `Model.model_validate_json()`. Gemini
  guarantees JSON shape but not semantics, so Pydantic validation + deterministic
  checks remain.
- **Provider abstraction:** a thin `LLMProvider` interface so Gemini can be
  swapped for Groq/other later without touching the pipeline.
- **Rulebook:** `rules/rbi_rules.yaml` holds hours, call caps, threat lexicon
  (English + Hinglish), consent phrases, severity weights, and clause references.
  Clause text is labeled "configurable — verify against official RBI Master
  Direction" to avoid presenting fabricated citations as fact.
- **Deterministic vs LLM split:** time-of-day and call-cap are pure Python;
  threat/consent/tone are LLM. Final risk score is computed deterministically in
  Python from all detected violations (reproducible, defensible).
- **Stack:** Python 3.10+, `streamlit`, `pydantic` v2, `google-genai`, `pyyaml`,
  `pandas`, `plotly`, `fpdf2`, `python-dotenv`, `pytest`.

## Task breakdown

Each task is test-driven and ends with a demoable increment.

### Task 1 — Project scaffold + config + dependencies
Create folder structure, `requirements.txt`, `.env.example`, and a config module
that loads model IDs and the rulebook path. README with pitch narrative.
- Test: config test asserts defaults load and a missing key raises a clear error.
- Demo: `pip install` succeeds; `import compliance` works.

### Task 2 — Pydantic data models
`Transcript`, `Violation`, `CallComplianceReport` with enums for severity and
compliance status.
- Test: valid build, enum enforcement, score bounds 0-100, JSON round-trip.
- Demo: build a report in a REPL, print validated JSON matching target schema.

### Task 3 — Rulebook + ingestion
Author `rbi_rules.yaml`. Implement ingestion for `.txt` and `.zip` with metadata
extraction from headers/filename, with graceful fallbacks.
- Test: parse a sample `.txt` and a `.zip`; validate rulebook structure.
- Demo: ingest `data/samples/` and print parsed transcripts + metadata.

### Task 4 — Deterministic checks + scoring
Time-of-day and call-cap checks; deterministic 0-100 risk scoring and status.
- Test: table-driven (7:45 PM -> time violation; 3 calls/day -> harassment; clean
  call -> 0 / COMPLIANT).
- Demo: run over samples, print violations + score, no API key needed.

### Task 5 — Gemini provider + LLM analyzer (structured output)
`LLMProvider` interface, `GeminiProvider` using structured output against the
Pydantic schema, analyzer prompt for consent / threats / tone. Parse + validate,
retry once, optional pro-model escalation.
- Test: mocked provider returning canned JSON; optional live smoke test gated by
  API key env var.
- Demo: analyze a Hinglish threat transcript, see the threat violation + quote.

### Task 6 — Pipeline orchestration
Wire ingest -> deterministic checks -> LLM analyzer -> aggregate -> score into
`pipeline.py`, single or batch, resilient to per-file errors.
- Test: end-to-end with mocked LLM over the sample set.
- Demo: run the pipeline over `data/samples/` and print a batch of reports.

### Task 7 — Streamlit dashboard + transcript deep-dive
Drag-and-drop upload, batch telemetry (compliance rate, violation distribution,
agent rankings) and a split-screen deep-dive with highlighted violation cards.
- Test: headless smoke run; unit tests on UI helpers.
- Demo: upload the sample batch, browse dashboard + deep-dive.

### Task 8 — PDF audit report export
`fpdf2` export: metadata, status, score, violation table, coaching summary,
timestamp. Download buttons. Unicode font for Hinglish.
- Test: PDF bytes generated and non-empty for a sample report.
- Demo: click export, open a generated PDF.

### Task 9 — Sample data, eval set, and pitch polish
Labeled samples per violation type, `eval/labeled_set.jsonl`, `run_eval.py`
reporting precision/recall. Finalize README + pitch narrative.
- Test: `run_eval.py` runs against fixed outputs and prints metrics; full suite
  green.
- Demo: run eval to show measured detection quality; walk the README pitch.

## Definition of done

- `pytest` suite green.
- App runs locally; deterministic checks work with no API key.
- With a key, LLM detection produces validated `CallComplianceReport`s.
- Dashboard, deep-dive, and PDF export all function on the sample batch.
- Eval script reports precision/recall on the labeled set.
