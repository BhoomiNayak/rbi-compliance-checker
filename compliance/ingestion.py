"""Transcript ingestion: parse .txt and .zip inputs into Transcript models.

Metadata (call id, agent id, customer id, timestamp, calls-today) is extracted
from a header block at the top of the transcript when present, and otherwise
falls back to filename hints and safe defaults so a bare transcript still works.

Header block format (case-insensitive keys), optionally followed by a '---'
separator, then the dialogue:

    Call_ID: TRANSCRIPT_8902
    Agent_ID: AGT_402
    Customer_ID: CUST_11876
    Call_Timestamp: 2026-09-22T19:45:00
    Call_Count_Today: 3
    ---
    [00:00] Agent: ...
"""

from __future__ import annotations

import io
import re
import zipfile
from datetime import datetime
from pathlib import Path

from .models import Transcript

_HEADER_LINE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_ ]*?)\s*[:=]\s*(.+?)\s*$")
_SEPARATOR = re.compile(r"^\s*-{3,}\s*$")

# Map various header key spellings to the Transcript fields.
_KEY_ALIASES = {
    "call_id": "call_id",
    "callid": "call_id",
    "agent_id": "agent_id",
    "agentid": "agent_id",
    "agent": "agent_id",
    "customer_id": "customer_id",
    "customerid": "customer_id",
    "customer": "customer_id",
    "call_timestamp": "timestamp",
    "timestamp": "timestamp",
    "call_time": "timestamp",
    "datetime": "timestamp",
    "call_count_today": "call_count_today",
    "calls_today": "call_count_today",
    "call_count": "call_count_today",
}


def _parse_timestamp(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    # Try ISO first, then a few common formats.
    candidates = [
        None,  # sentinel for fromisoformat
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%dT%H:%M:%S",
    ]
    for fmt in candidates:
        try:
            if fmt is None:
                return datetime.fromisoformat(value)
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _metadata_from_filename(filename: str) -> dict:
    """Best-effort metadata from a filename like TRANSCRIPT_8902_AGT_402.txt."""
    stem = Path(filename).stem
    meta: dict = {}
    call_match = re.search(r"(TRANSCRIPT[_-]?[A-Za-z0-9]+)", stem, re.IGNORECASE)
    if call_match:
        meta["call_id"] = call_match.group(1)
    agent_match = re.search(r"(AGT[_-]?[A-Za-z0-9]+)", stem, re.IGNORECASE)
    if agent_match:
        meta["agent_id"] = agent_match.group(1)
    return meta


def parse_transcript_text(content: str, filename: str = "transcript.txt") -> Transcript:
    """Parse raw transcript text (with optional header) into a Transcript."""
    lines = content.splitlines()
    meta: dict = {}
    body_start = 0
    in_header = True

    for i, line in enumerate(lines):
        if _SEPARATOR.match(line):
            body_start = i + 1
            break
        if not in_header:
            break
        match = _HEADER_LINE.match(line)
        if match and not line.lstrip().startswith("["):
            raw_key = match.group(1).strip().lower().replace(" ", "_")
            field = _KEY_ALIASES.get(raw_key)
            if field:
                meta[field] = match.group(2).strip()
                body_start = i + 1
                continue
        # First non-header, non-blank line ends the header scan.
        if line.strip():
            in_header = False
            body_start = i
            break

    body = "\n".join(lines[body_start:]).strip()
    if not body:
        # No separator / header consumed everything -> treat whole thing as body.
        body = content.strip()

    # Fill gaps from filename, then defaults.
    file_meta = _metadata_from_filename(filename)
    call_id = meta.get("call_id") or file_meta.get("call_id") or Path(filename).stem
    agent_id = meta.get("agent_id") or file_meta.get("agent_id") or "UNKNOWN"
    customer_id = meta.get("customer_id") or "UNKNOWN"
    timestamp = _parse_timestamp(meta["timestamp"]) if "timestamp" in meta else None

    try:
        call_count = int(meta.get("call_count_today", 1))
    except (TypeError, ValueError):
        call_count = 1

    return Transcript(
        call_id=call_id,
        agent_id=agent_id,
        customer_id=customer_id,
        timestamp=timestamp,
        call_count_today=call_count,
        text=body,
    )


def load_txt(path: str | Path) -> Transcript:
    """Load a single .txt transcript from disk."""
    path = Path(path)
    content = path.read_text(encoding="utf-8", errors="replace")
    return parse_transcript_text(content, path.name)


def load_zip_bytes(data: bytes) -> list[Transcript]:
    """Load all .txt transcripts from a .zip archive given as raw bytes."""
    transcripts: list[Transcript] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in sorted(zf.namelist()):
            if name.endswith("/") or not name.lower().endswith(".txt"):
                continue
            if name.startswith("__MACOSX"):
                continue
            raw = zf.read(name).decode("utf-8", errors="replace")
            transcripts.append(parse_transcript_text(raw, Path(name).name))
    return transcripts


def load_zip(path: str | Path) -> list[Transcript]:
    """Load all .txt transcripts from a .zip archive on disk."""
    return load_zip_bytes(Path(path).read_bytes())


def load_directory(path: str | Path) -> list[Transcript]:
    """Load every .txt transcript in a directory (non-recursive)."""
    path = Path(path)
    return [load_txt(p) for p in sorted(path.glob("*.txt"))]


def ingest_upload(filename: str, data: bytes) -> list[Transcript]:
    """Dispatch an uploaded file (by name) to the right loader."""
    lower = filename.lower()
    if lower.endswith(".zip"):
        return load_zip_bytes(data)
    if lower.endswith(".txt"):
        text = data.decode("utf-8", errors="replace")
        return [parse_transcript_text(text, filename)]
    raise ValueError(f"Unsupported file type: {filename} (expected .txt or .zip)")
