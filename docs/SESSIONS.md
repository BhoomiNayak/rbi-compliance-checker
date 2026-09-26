# Session-by-Session Build Plan

The project is built in **5 working sessions**. Session 0 (this one) is already
done: planning docs and scaffold. Each build session ends with something you can
run and demo, so if time runs short before tomorrow the earlier sessions already
give a working product.

Legend: 🟢 no API key needed · 🔵 needs `GEMINI_API_KEY`

---

## Session 0 — Planning & scaffold ✅ (DONE)
**Goal:** Lock decisions, write docs, lay down the skeleton.
- README, PLAN, ARCHITECTURE, RBI_RULES, PITCH, SESSIONS docs.
- `requirements.txt`, `.env.example`, `.gitignore`.
- `rules/rbi_rules.yaml`, `compliance/` package, sample transcripts.
**Deliverable:** repo scaffold + full plan. (Maps to Task 1.)

---

## Session 1 — Core engine, offline 🟢
**Goal:** A working deterministic compliance engine with validated data models —
no LLM yet, fully testable without a key.
- `compliance/config.py` — env + model IDs + rulebook path loader.
- `compliance/models.py` — Pydantic `Transcript`, `Violation`, `CallComplianceReport`.
- `compliance/ingestion.py` — parse `.txt` + `.zip`, extract metadata.
- `compliance/rules.py` — rulebook loader + time-of-day + call-cap checks.
- `compliance/scoring.py` — deterministic 0-100 score + status.
- `tests/` for each of the above.
**Deliverable:** `python -m compliance.rules data/samples` prints violations +
scores for the samples. `pytest` green. (Maps to Tasks 1-4.)

---

## Session 2 — LLM analyzer with structured output 🔵
**Goal:** Add Gemini-powered language judgment (Hinglish threats, consent, tone).
- `compliance/llm_provider.py` — `LLMProvider` interface + `GeminiProvider`.
- `compliance/analyzer.py` — prompt + native structured output + Pydantic parse,
  one retry, optional pro-model escalation, transcript-as-untrusted-data handling.
- Tests with a **mocked** provider (no network); one optional live smoke test.
**Deliverable:** analyze the Hinglish sample and see the threat violation with a
verbatim quote. (Maps to Task 5.)

---

## Session 3 — Pipeline + Streamlit dashboard & deep-dive 🔵/🟢
**Goal:** Tie it together and make it visual.
- `compliance/pipeline.py` — ingest → deterministic → LLM → aggregate → score,
  single + batch, resilient to per-file errors.
- `app.py` — upload (drag-and-drop `.txt`/`.zip`), batch telemetry (compliance
  rate, violation distribution, agent risk rankings via Plotly), split-screen
  transcript deep-dive with highlighted violation cards.
- **UI follows `docs/DESIGN_SYSTEM.md`** — Craft AI's warm, editorial, card-based
  theme (cream background, brick/terracotta accent, pastel tiles). Custom CSS via
  `assets/theme.css` + `.streamlit/config.toml`, not the default Streamlit look.
- Graceful "no API key" mode running deterministic checks only.
**Deliverable:** `streamlit run app.py`, upload the sample batch, browse the
dashboard and a deep-dive. (Maps to Tasks 6-7.)

---

## Session 4 — PDF export, eval set, polish 🔵/🟢
**Goal:** Regulator-ready output and measured quality; final pitch polish.
- `compliance/report_pdf.py` — `fpdf2` per-call + batch audit PDF (Unicode font
  for Hinglish); download buttons wired into the UI.
- `eval/labeled_set.jsonl` + `eval/run_eval.py` — precision/recall on violation
  detection.
- Final README/PITCH pass, screenshots, and a `data/samples` set covering every
  violation type.
**Deliverable:** one-click PDF export works; `python eval/run_eval.py` prints
precision/recall; full `pytest` suite green. (Maps to Tasks 8-9.)

---

## Suggested schedule to hit "tomorrow"

| When | Session | Rough effort |
| --- | --- | --- |
| Now (done) | 0 | — |
| Today evening | 1 | ~1.5 h |
| Today evening | 2 | ~1 h |
| Tomorrow morning | 3 | ~2 h |
| Tomorrow midday | 4 | ~1.5 h |

If you get an API key set up before Session 2, everything demos end-to-end. If
not, Sessions 1 and 3 still give a working deterministic app you can show, and
the LLM layer slots in the moment a key is available.

## Fallback / cut-scope order (if time is tight)
1. Ship Sessions 1 + 3 (deterministic app + dashboard) — already demoable.
2. Add Session 2 (LLM threats) — the headline feature.
3. Add Session 4 PDF export.
4. Add Session 4 eval set last (nice-to-have credibility booster).
