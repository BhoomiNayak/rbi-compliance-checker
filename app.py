"""RBI Compliance & Call Quality Inspector — Streamlit app.

Craft AI-inspired UI (see docs/DESIGN_SYSTEM.md). Two views:
  1. Dashboard  — batch telemetry: compliance rate, violation mix, agent rankings.
  2. Deep-dive  — split screen: raw transcript + highlighted violation cards.

Runs with no API key (deterministic checks only) or with a Gemini key
(full LLM threat/consent/tone analysis).
"""

from __future__ import annotations

import html
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from compliance.config import get_config
from compliance.ingestion import ingest_upload, load_directory
from compliance.models import CallComplianceReport, ComplianceStatus, Severity
from compliance.pipeline import AnalysisResult, analyze_batch
from compliance.report_pdf import build_batch_pdf, build_call_pdf

PROJECT_ROOT = Path(__file__).resolve().parent
SAMPLES_DIR = PROJECT_ROOT / "data" / "samples"

BRICK = "#C6482B"
SAND = "#C79A3A"
SAGE = "#4F7A52"
MUTED = "#6B6259"

STATUS_PILL = {
    ComplianceStatus.COMPLIANT: ("pill-compliant", "COMPLIANT"),
    ComplianceStatus.REVIEW: ("pill-review", "REVIEW"),
    ComplianceStatus.NON_COMPLIANT: ("pill-noncompliant", "NON-COMPLIANT"),
}
SEVERITY_ORDER = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}


# --------------------------------------------------------------------------- #
# Setup
# --------------------------------------------------------------------------- #

st.set_page_config(
    page_title="RBI Compliance & Call Quality Inspector",
    page_icon="◆",
    layout="wide",
)


def _load_css() -> None:
    css = (PROJECT_ROOT / "assets" / "theme.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


_load_css()


def _hero() -> None:
    st.markdown(
        """
        <div class="rbi-hero">
          <div class="rbi-logo">◆</div>
          <div>
            <h1 style="margin:0;font-size:1.6rem;">RBI Compliance &amp; Call Quality Inspector</h1>
          </div>
        </div>
        <p class="rbi-sub">Audit debt-collection calls for RBI recovery-agent
        violations — Hinglish threat detection, consent &amp; timing checks, and
        regulator-ready reports. The compliance layer for AI collections agents.</p>
        """,
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- #
# Rendering helpers
# --------------------------------------------------------------------------- #

def _status_pill(status: ComplianceStatus) -> str:
    cls, label = STATUS_PILL[status]
    return f'<span class="pill {cls}">{label}</span>'


def _tile(label: str, value: str, variant: str) -> str:
    return (
        f'<div class="tile tile-{variant}">'
        f'<div class="tile-label">{html.escape(label)}</div>'
        f'<div class="tile-value">{html.escape(str(value))}</div></div>'
    )


def _violation_card(v) -> str:
    sev = v.severity.value.lower()
    quote = html.escape(v.quote)
    conf = f" · conf {v.confidence:.2f}" if v.confidence is not None else ""
    src = v.source.value
    return (
        f'<div class="viol viol-{sev}">'
        f'<div class="viol-head"><span class="viol-type">{html.escape(v.type)}</span>'
        f'<span class="viol-sev sev-{sev}">{v.severity.value}</span></div>'
        f'<div class="viol-quote">“{quote}”</div>'
        f'<div class="viol-meta">@ {html.escape(v.timestamp_offset)}{conf}'
        f'<span class="src-badge">{src}</span><br>'
        f'{html.escape(v.rbi_clause)}</div>'
        f"</div>"
    )


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #

def render_dashboard(results: list[AnalysisResult]) -> None:
    reports = [r.report for r in results]
    total = len(reports)
    compliant = sum(1 for r in reports if r.compliance_status is ComplianceStatus.COMPLIANT)
    non_compliant = sum(
        1 for r in reports if r.compliance_status is ComplianceStatus.NON_COMPLIANT
    )
    rate = round(100 * compliant / total) if total else 0
    avg_risk = round(sum(r.overall_risk_score for r in reports) / total) if total else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(_tile("Portfolio compliance rate", f"{rate}%", "sage"), unsafe_allow_html=True)
    c2.markdown(_tile("Calls audited", total, "sand"), unsafe_allow_html=True)
    c3.markdown(_tile("Non-compliant", non_compliant, "pink"), unsafe_allow_html=True)
    c4.markdown(_tile("Avg risk score", avg_risk, "maroon"), unsafe_allow_html=True)

    st.write("")
    left, right = st.columns(2)

    # Violation distribution by type
    viol_rows = [
        {"type": v.type, "severity": v.severity.value}
        for r in reports
        for v in r.violations
    ]
    with left:
        st.markdown("#### Violation distribution")
        if viol_rows:
            df = pd.DataFrame(viol_rows)
            counts = df.groupby("type").size().reset_index(name="count").sort_values("count")
            fig = px.bar(
                counts, x="count", y="type", orientation="h",
                color_discrete_sequence=[BRICK],
            )
            fig.update_layout(
                height=320, margin=dict(l=0, r=10, t=10, b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                yaxis_title="", xaxis_title="",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No violations detected in this batch.")

    # Agent risk rankings
    with right:
        st.markdown("#### Agent risk ranking")
        agent_df = (
            pd.DataFrame(
                [{"agent": r.agent_id, "risk": r.overall_risk_score} for r in reports]
            )
            .groupby("agent")["risk"].mean().reset_index()
            .sort_values("risk", ascending=True)
        )
        fig2 = px.bar(
            agent_df, x="risk", y="agent", orientation="h",
            color="risk", color_continuous_scale=["#C7D2C0", "#EBD9BE", "#C6482B"],
        )
        fig2.update_layout(
            height=320, margin=dict(l=0, r=10, t=10, b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            yaxis_title="", xaxis_title="avg risk score", coloraxis_showscale=False,
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Portfolio table
    hdr, dl = st.columns([3, 1])
    hdr.markdown("#### Calls")
    dl.download_button(
        "Export batch audit PDF",
        data=build_batch_pdf(reports),
        file_name="rbi_batch_audit.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
    table = pd.DataFrame(
        [
            {
                "Call": r.call_id,
                "Agent": r.agent_id,
                "Status": STATUS_PILL[r.compliance_status][1],
                "Risk": r.overall_risk_score,
                "On-time": "yes" if r.time_of_day_compliant else "no",
                "Consent": "yes" if r.consent_given else "no",
                "Violations": len(r.violations),
            }
            for r in reports
        ]
    )
    st.dataframe(table, use_container_width=True, hide_index=True)


# --------------------------------------------------------------------------- #
# Deep-dive
# --------------------------------------------------------------------------- #

def render_deepdive(results: list[AnalysisResult], transcripts_by_index: list) -> None:
    reports = [r.report for r in results]
    if not reports:
        st.info("No calls to display.")
        return
    labels = [
        f"{r.call_id} — {STATUS_PILL[r.compliance_status][1]} (risk {r.overall_risk_score})"
        for r in reports
    ]
    idx = st.selectbox("Select a call", range(len(reports)), format_func=lambda i: labels[i])
    result = results[idx]
    report = result.report

    st.markdown(
        f"### {report.call_id} &nbsp; {_status_pill(report.compliance_status)}",
        unsafe_allow_html=True,
    )
    meta = f"Agent {report.agent_id} · Customer {report.customer_id} · Risk {report.overall_risk_score}/100"
    if report.timestamp:
        meta += f" · {report.timestamp:%Y-%m-%d %H:%M}"
    st.caption(meta)
    if not result.llm_used:
        st.warning(" · ".join(result.notes) or "Deterministic-only analysis.")

    left, right = st.columns([1.1, 1])
    with left:
        st.markdown("#### Transcript")
        text = transcripts_by_index[idx] if idx < len(transcripts_by_index) else ""
        st.markdown(f'<div class="transcript">{html.escape(text)}</div>', unsafe_allow_html=True)

    with right:
        st.markdown(f"#### Violations ({len(report.violations)})")
        if report.violations:
            for v in sorted(report.violations, key=lambda x: SEVERITY_ORDER[x.severity]):
                st.markdown(_violation_card(v), unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="card">No violations detected — call is compliant.</div>',
                unsafe_allow_html=True,
            )
        if report.agent_coaching_summary:
            st.markdown("#### Agent coaching summary")
            st.markdown(
                f'<div class="card">{html.escape(report.agent_coaching_summary)}</div>',
                unsafe_allow_html=True,
            )
        st.download_button(
            "Export this call's audit PDF",
            data=build_call_pdf(report),
            file_name=f"rbi_audit_{report.call_id}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def _run(transcripts) -> None:
    if not transcripts:
        st.error("No transcripts found in the upload.")
        return
    bar = st.progress(0.0, text="Analyzing calls...")
    results = analyze_batch(
        transcripts, progress=lambda done, total: bar.progress(done / total)
    )
    bar.empty()
    # Key transcript text by list index (not call_id) so duplicate call_ids do
    # not collide and show the wrong transcript in the deep-dive.
    st.session_state["transcripts_by_index"] = [t.text for t in transcripts]
    st.session_state["results"] = results


def main() -> None:
    _hero()
    cfg = get_config()

    with st.sidebar:
        st.markdown("### Ingestion")
        if cfg.llm_enabled:
            st.success(f"LLM enabled · {cfg.model}")
        else:
            st.warning("No API key — deterministic checks only. Add GEMINI_API_KEY in .env for full analysis.")

        uploaded = st.file_uploader(
            "Drop .txt transcripts or a .zip", type=["txt", "zip"], accept_multiple_files=True
        )
        run_upload = st.button("Analyze uploaded", use_container_width=True)
        st.markdown("---")
        run_samples = st.button("Load sample batch", use_container_width=True)

    if run_samples:
        _run(load_directory(SAMPLES_DIR))
    if run_upload and uploaded:
        transcripts = []
        for f in uploaded:
            transcripts.extend(ingest_upload(f.name, f.getvalue()))
        _run(transcripts)

    results = st.session_state.get("results")
    if not results:
        st.info("Load the sample batch or upload transcripts from the sidebar to begin.")
        return

    tab_dash, tab_deep = st.tabs(["Dashboard", "Transcript deep-dive"])
    with tab_dash:
        render_dashboard(results)
    with tab_deep:
        render_deepdive(results, st.session_state.get("transcripts_by_index", []))


if __name__ == "__main__":
    main()
