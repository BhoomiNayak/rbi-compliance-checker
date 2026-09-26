"""RBI Compliance & Call Quality Inspector — core package.

Modules (built across the sessions in docs/SESSIONS.md):
    config       — env + model IDs + rulebook path
    models       — Pydantic data model (Transcript, Violation, CallComplianceReport)
    ingestion    — .txt / .zip parsing + metadata extraction
    rules        — rulebook loader + deterministic checks
    llm_provider — LLMProvider interface + GeminiProvider
    analyzer     — LLM prompt + structured-output call + parsing
    scoring      — deterministic risk scoring + status
    pipeline     — orchestration
    report_pdf   — fpdf2 audit report
"""

__version__ = "0.1.0"
