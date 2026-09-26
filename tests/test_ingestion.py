import io
import zipfile
from datetime import datetime

from compliance.ingestion import (
    ingest_upload,
    load_zip_bytes,
    parse_transcript_text,
)

HEADERED = """Call_ID: TRANSCRIPT_8902
Agent_ID: AGT_402
Customer_ID: CUST_11876
Call_Timestamp: 2026-09-22T19:45:00
Call_Count_Today: 3
---
[00:00] Agent: Haan ji.
[01:22] Agent: police leke aaunga.
"""

BARE = "[00:00] Agent: Hello, this is a reminder about your EMI."


def test_parse_headered_transcript():
    t = parse_transcript_text(HEADERED, "TRANSCRIPT_8902_AGT_402.txt")
    assert t.call_id == "TRANSCRIPT_8902"
    assert t.agent_id == "AGT_402"
    assert t.customer_id == "CUST_11876"
    assert t.call_count_today == 3
    assert t.timestamp == datetime(2026, 9, 22, 19, 45, 0)
    assert "police leke aaunga" in t.text
    assert "Call_ID" not in t.text  # header stripped from body


def test_parse_bare_transcript_uses_filename_and_defaults():
    t = parse_transcript_text(BARE, "TRANSCRIPT_9001_AGT_777.txt")
    assert t.call_id == "TRANSCRIPT_9001"
    assert t.agent_id == "AGT_777"
    assert t.customer_id == "UNKNOWN"
    assert t.call_count_today == 1
    assert t.timestamp is None
    assert "EMI" in t.text


def test_ingest_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("TRANSCRIPT_8902_AGT_402.txt", HEADERED)
        zf.writestr("bare_AGT_111.txt", BARE)
        zf.writestr("__MACOSX/junk.txt", "ignore me")
    transcripts = load_zip_bytes(buf.getvalue())
    assert len(transcripts) == 2
    ids = {t.call_id for t in transcripts}
    assert "TRANSCRIPT_8902" in ids


def test_ingest_upload_dispatch():
    result = ingest_upload("x.txt", BARE.encode("utf-8"))
    assert len(result) == 1
    assert result[0].text.startswith("[00:00]")


def test_ingest_upload_rejects_unknown_type():
    import pytest

    with pytest.raises(ValueError):
        ingest_upload("x.pdf", b"data")
