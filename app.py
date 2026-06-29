"""
app.py - the Flask web server.

This is the part the outside world talks to. It exposes three endpoints:

  POST /submit   - send text, get back an attribution + confidence + label
  POST /appeal   - contest a classification by content_id
  GET  /log      - read the audit log (newest entries first)

Flask basics, since this is the entry point:
  - `app = Flask(__name__)` creates the web application.
  - `@app.route("/path", methods=[...])` ties a URL + HTTP method to a function.
  - `request.get_json()` reads the JSON body the caller sent.
  - `jsonify({...})` turns a dict into a JSON HTTP response.
  - returning `(body, status_code)` sets the HTTP status (200 ok, 400 bad request, etc.).
  - run this file directly and Flask serves it on http://localhost:5000.
"""

import uuid
from datetime import datetime, timezone

from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import detection
import store

app = Flask(__name__)

# Rate limiting. Flask-Limiter 3.x+ needs a storage backend; "memory://" keeps the
# counters in RAM, which is fine for local dev / this project.
# get_remote_address means "count requests per client IP address".
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],            # no global limit; we apply limits per-route
    storage_uri="memory://",
)


def _now():
    return datetime.now(timezone.utc).isoformat()


@app.route("/", methods=["GET"])
def index():
    """A tiny home page so you can confirm the server is up in a browser."""
    return jsonify({
        "service": "Provenance Guard",
        "endpoints": {
            "POST /submit": "classify text  (body: {text, creator_id})",
            "POST /appeal": "contest a result (body: {content_id, creator_reasoning})",
            "GET /log": "view the audit log",
        },
    })


@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")  # see README for why these numbers
def submit():
    """Classify a piece of text and log the decision."""
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    creator_id = (body.get("creator_id") or "").strip()

    # Validate input early and return a clear 400 if something's missing.
    if not text:
        return jsonify({"error": "Field 'text' is required."}), 400
    if not creator_id:
        return jsonify({"error": "Field 'creator_id' is required."}), 400

    # Run both detection signals + scoring + label.
    result = detection.analyze(text)

    # Build the full record we return and store.
    record = {
        "content_id": str(uuid.uuid4()),
        "creator_id": creator_id,
        "timestamp": _now(),
        "text_preview": text[:120],          # a snippet so the log is readable
        "attribution": result["attribution"],
        "confidence": result["confidence"],
        "label": result["label"],
        "signals": result["signals"],
        "status": "classified",
    }

    store.record_submission(record)
    return jsonify(record), 200


@app.route("/appeal", methods=["POST"])
def appeal():
    """Let a creator contest a classification. Sets status to under_review and logs it."""
    body = request.get_json(silent=True) or {}
    content_id = (body.get("content_id") or "").strip()
    reasoning = (body.get("creator_reasoning") or "").strip()

    if not content_id:
        return jsonify({"error": "Field 'content_id' is required."}), 400
    if not reasoning:
        return jsonify({"error": "Field 'creator_reasoning' is required."}), 400

    record = store.record_appeal(content_id, reasoning)
    if record is None:
        return jsonify({"error": f"No content found with id '{content_id}'."}), 404

    return jsonify({
        "content_id": content_id,
        "status": "under_review",
        "message": "Appeal received. This content is now under review by a human.",
    }), 200


@app.route("/log", methods=["GET"])
def log():
    """Return recent audit entries (newest first). In production this would need auth."""
    return jsonify({"entries": store.read_log()})


@app.errorhandler(429)
def ratelimit_handler(e):
    """Return rate-limit rejections as clean JSON instead of an HTML error page."""
    return jsonify({
        "error": "Rate limit exceeded. Please slow down and try again later.",
        "detail": str(e.description),
    }), 429


if __name__ == "__main__":
    # debug=True auto-reloads on file changes and shows errors; fine for development.
    app.run(host="127.0.0.1", port=5000, debug=True)
