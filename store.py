"""
store.py - where Provenance Guard keeps its data.

Everything lives in a single JSON file (store.json) so you can literally open it
and read the whole history. Two things are kept:

  contents : a dict of {content_id: record}   -> the current state of each submission
  audit    : a list of events (append-only)    -> the audit log, never edited in place

A submission adds one record to `contents` AND one event to `audit`.
An appeal updates the record's status in `contents` AND adds another event to `audit`.
"""

import json
import os
import threading
from datetime import datetime, timezone

# The file we read/write. Sits next to this script.
STORE_PATH = os.path.join(os.path.dirname(__file__), "store.json")

# A lock so two requests can't corrupt the file by writing at the same time.
_lock = threading.Lock()


def _now():
    """Current time as an ISO-8601 UTC string, e.g. 2026-06-28T14:32:10.123456+00:00."""
    return datetime.now(timezone.utc).isoformat()


def _load():
    """Read the JSON file. If it doesn't exist yet, start with an empty structure."""
    if not os.path.exists(STORE_PATH):
        return {"contents": {}, "audit": []}
    with open(STORE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data):
    """Write the whole structure back to the file."""
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def record_submission(record):
    """
    Save a classified submission.

    `record` is the dict the endpoint built (content_id, scores, label, etc.).
    We store it under its content_id and also append a "submission" event to the log.
    """
    with _lock:
        data = _load()
        data["contents"][record["content_id"]] = record
        data["audit"].append({
            "event": "submission",
            "timestamp": record["timestamp"],
            "content_id": record["content_id"],
            "creator_id": record["creator_id"],
            "attribution": record["attribution"],
            "confidence": record["confidence"],
            "llm_score": record["signals"]["llm_score"],
            "style_score": record["signals"]["style_score"],
            "status": record["status"],
        })
        _save(data)


def get_content(content_id):
    """Return the stored record for a content_id, or None if we've never seen it."""
    with _lock:
        return _load()["contents"].get(content_id)


def record_appeal(content_id, creator_reasoning):
    """
    Handle an appeal: flip the content's status to 'under_review' and log the appeal
    next to a snapshot of the original decision.

    Returns the updated record, or None if the content_id is unknown.
    """
    with _lock:
        data = _load()
        record = data["contents"].get(content_id)
        if record is None:
            return None

        record["status"] = "under_review"
        record["appeal"] = {
            "creator_reasoning": creator_reasoning,
            "timestamp": _now(),
        }
        data["contents"][content_id] = record

        # The appeal event keeps a copy of the original decision so a reviewer
        # sees the reasoning and the original scores side by side.
        data["audit"].append({
            "event": "appeal",
            "timestamp": record["appeal"]["timestamp"],
            "content_id": content_id,
            "creator_id": record["creator_id"],
            "status": "under_review",
            "appeal_reasoning": creator_reasoning,
            "original_attribution": record["attribution"],
            "original_confidence": record["confidence"],
            "llm_score": record["signals"]["llm_score"],
            "style_score": record["signals"]["style_score"],
        })
        _save(data)
        return record


def read_log(limit=50):
    """Return the most recent audit events, newest first."""
    with _lock:
        events = _load()["audit"]
    return list(reversed(events))[:limit]
