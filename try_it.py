"""
try_it.py - type your own text and watch Provenance Guard classify it, live.

Start the server first (python app.py) in one terminal, then in another:
    python try_it.py

Paste or type some text, press Enter twice, and you'll see the attribution,
the confidence score, both signal scores, and the reader-facing label.
Type 'quit' to exit.
"""

import sys
import json
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")  # so emoji in labels print on Windows
except Exception:
    pass

BASE = "http://localhost:5000"


def classify(text):
    """Send text to the running server and return the parsed JSON result."""
    data = json.dumps({"text": text, "creator_id": "demo-user"}).encode("utf-8")
    req = urllib.request.Request(
        BASE + "/submit",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def read_text():
    """Read one line of text and submit it. Empty line is ignored; 'quit' exits."""
    print("\nType or paste some text and press Enter (or type 'quit' to exit):")
    while True:
        try:
            line = input("> ")
        except EOFError:
            return None
        if line.strip().lower() == "quit":
            return None
        if line.strip() == "":       # ignore empty Enter, just ask again
            continue
        return line


print("=" * 70)
print(" Provenance Guard - type some text and see how it's classified")
print("=" * 70)

while True:
    text = read_text()
    if text is None:
        print("\nBye!")
        break

    try:
        result = classify(text)
    except Exception as e:
        print(f"\n[!] Could not reach the server at {BASE} - is 'python app.py' running?")
        print(f"    ({e})")
        continue

    s = result["signals"]
    print("\n" + "-" * 70)
    print(f"  ATTRIBUTION : {result['attribution']}")
    print(f"  CONFIDENCE  : {result['confidence']}  (probability it's AI, 0-1)")
    print(f"  SIGNAL 1 (LLM)        : {s['llm_score']}   - {s['llm_rationale']}")
    print(f"  SIGNAL 2 (stylometry) : {s['style_score']}")
    print(f"  LABEL SHOWN TO READER :\n    {result['label']}")
    print("-" * 70)
