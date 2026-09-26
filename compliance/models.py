"""Pydantic data model — the contract for compliance telemetry.

These models are the single source of truth. The LLM is asked to fill the
violation schema via structured output; Python validates it; the dashboard and
PDF report consume it.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Severity(str, Enum):
    """Violation severity levels."""

    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class ComplianceStatus(str, Enum):
    """Overall compliance status for a call."""

    COMPLIANT = "COMPLIANT"
    REVIEW = "REVIEW"
    NON_COMPLIANT = "NON_COMPLIANT"


class ViolationSource(str, Enum):
    """Where a violation was detected."""

    DETERMINISTIC = "deterministic"
    LLM = "llm"


class Transcript(BaseModel):
    """A single call transcript plus its metadata."""

    call_id: str
    agent_id: str
    customer_id: str = "UNKNOWN"
    timestamp: datetime | None = None
    call_count_today: int = 1
    text: str = ""

    @field_validator("call_count_today")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("call_count_today must be >= 0")
        return v


class Violation(BaseModel):
    """A single detected compliance violation."""

    type: str = Field(description="Short violation type, e.g. 'Illegal Threat Term'.")
    severity: Severity
    timestamp_offset: str = Field(
        default="00:00", description="Offset within the call as mm:ss."
    )
    quote: str = Field(description="Verbatim offending text from the transcript.")
    rbi_clause: str = Field(description="RBI clause reference from the rulebook.")
    source: ViolationSource = ViolationSource.LLM
    confidence: float | None = Field(
        default=None, description="LLM confidence 0-1 where applicable."
    )

    @field_validator("confidence")
    @classmethod
    def _confidence_range(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("confidence must be between 0 and 1")
        return v


class CallComplianceReport(BaseModel):
    """The full validated compliance result for one call."""

    call_id: str
    agent_id: str
    customer_id: str = "UNKNOWN"
    timestamp: datetime | None = None
    compliance_status: ComplianceStatus = ComplianceStatus.COMPLIANT
    overall_risk_score: int = Field(default=0, ge=0, le=100)
    time_of_day_compliant: bool = True
    consent_given: bool = True
    call_count_today: int = 1
    violations: list[Violation] = Field(default_factory=list)
    agent_coaching_summary: str = ""


class LLMFinding(BaseModel):
    """Sub-schema the LLM fills via structured output (language judgment only)."""

    consent_given: bool = Field(
        description="True if a recording/identity disclosure was made early in the call."
    )
    violations: list[Violation] = Field(
        default_factory=list,
        description="Threat, coercion, and tone-escalation violations found.",
    )
    agent_coaching_summary: str = Field(
        default="", description="One-paragraph coaching summary for the agent."
    )
