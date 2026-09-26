# RBI Rules & Rulebook

This document explains the compliance rules the engine checks and how they map to
the configurable rulebook at `rules/rbi_rules.yaml`.

## Regulatory disclaimer (read first)

The RBI clause references in the rulebook are **configurable placeholders**. They
must be verified against the official
[RBI Master Direction on Recovery Agents / Fair Practices Code](https://www.rbi.org.in)
before any real regulatory use. This tool is decision-support and QA tooling, not
legal advice. Clause numbers should never be presented to a regulator without
verification against the current official text.

## Rules covered

### 1. Time-of-day (deterministic)
Collection calls to borrowers should be placed within permissible hours.
Widely-referenced RBI Fair Practices guidance is **08:00 - 19:00** local time.
The engine flags any call whose start timestamp falls outside this window.
- Detection: pure Python timestamp comparison (no LLM).
- Configurable via `hours.start` / `hours.end`.

### 2. Recording-consent disclosure (LLM-assisted)
Mandatory recording/identity disclosures should appear early in the call. The
analyzer checks whether a consent/disclosure statement is present in the opening
segment.
- Detection: LLM, guided by `consent.phrases`.

### 3. Threat & coercion, incl. Hinglish (LLM)
Illegal coercion includes threats of police, jail, arrest, court action,
unauthorised home visits, and public shaming (beizzati). The engine evaluates
both English and Hinglish / code-switched phrasing contextually — a mention is
not automatically a violation; a threat is.
- Detection: LLM, seeded with `threats.lexicon` (English + Hinglish).

### 4. Re-contact / harassment cap (deterministic) + tone (LLM)
Excessive outreach is flagged when calls-today exceeds the cap (default **> 2**).
Aggressive tone escalation is assessed by the LLM.
- Detection: call-cap is Python; tone is LLM.
- Configurable via `harassment.max_calls_per_day`.

## Rulebook structure (`rules/rbi_rules.yaml`)

```yaml
hours:            # permissible calling window
  start: "08:00"
  end:   "19:00"
harassment:
  max_calls_per_day: 2
consent:
  phrases: [ ... ]  # disclosure phrases to look for
threats:
  lexicon:          # seed terms (English + Hinglish); LLM judges context
    english: [ police, jail, arrest, court, ... ]
    hinglish: [ "police leke aaunga", "ghar aa jaunga", beizzati, ... ]
severity_weights:   # deterministic scoring contribution
  CRITICAL: 40
  WARNING:  20
  INFO:     5
thresholds:
  non_compliant_score: 40
  review_score: 10
clauses:            # CONFIGURABLE placeholders - verify before regulatory use
  time_of_day: "RBI Fair Practices Code - permissible calling hours (verify clause)"
  threat:      "RBI Master Direction - prohibition of harassment & coercion (verify clause)"
  consent:     "RBI recording/disclosure requirement (verify clause)"
  harassment:  "RBI limits on frequency of contact (verify clause)"
```

## Editing the rulebook

Compliance reviewers can edit `rbi_rules.yaml` directly. On the next run the
engine picks up the new hours, caps, lexicon, weights, thresholds, and clause
text — no code changes required.
