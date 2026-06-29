"""
demo.py - a tiny client that exercises the running Provenance Guard server.

Run the server first (python app.py) in one terminal, then in another:
    python demo.py

It submits a human-sounding text and an AI-sounding text, files an appeal on one,
and prints the audit log - i.e. a full tour of every feature, no curl needed.
"""

import sys
import json
import urllib.request

# Make sure emoji in the labels print fine on Windows consoles.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = "http://localhost:5000"


def call(method, path, body=None):
    """Send an HTTP request to the server and return the parsed JSON response."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def line():
    print("=" * 70)


# 1) Submit a casual, human-sounding piece -------------------------------------------
line()
print("1) SUBMIT a casual human-sounding note")
line()
status, human = call("POST", "/submit", {
    "text": ("ok so i finally tried that ramen place downtown and honestly? "
             "underwhelming. broth was fine but WAY too salty and i was thirsty "
             "for hours after. probably wont go back unless someone drags me"),
    "creator_id": "demo-human",
})
print("attribution:", human["attribution"], "| confidence:", human["confidence"])
print("label:", human["label"])

# 2) Submit a generic, AI-sounding piece ---------------------------------------------
print()
line()
print("2) SUBMIT a generic AI-sounding paragraph")
line()
status, ai = call("POST", "/submit", {
    "text": ("Artificial intelligence represents a transformative paradigm shift in "
             "modern society. It is important to note that while the benefits are "
             "numerous, it is equally essential to consider the ethical implications. "
             "Furthermore, stakeholders must collaborate to ensure responsible deployment."),
    "creator_id": "demo-ai",
})
print("attribution:", ai["attribution"], "| confidence:", ai["confidence"])
print("label:", ai["label"])
print("signals:", json.dumps(ai["signals"]["llm_score"]), "(llm) /",
      ai["signals"]["style_score"], "(style)")

# 3) Appeal the AI classification ----------------------------------------------------
print()
line()
print("3) APPEAL the AI result (content_id =", ai["content_id"], ")")
line()
status, appeal = call("POST", "/appeal", {
    "content_id": ai["content_id"],
    "creator_reasoning": "I wrote this myself, I just write in a formal style.",
})
print(json.dumps(appeal, indent=2))

# 4) Read the audit log --------------------------------------------------------------
print()
line()
print("4) AUDIT LOG (newest first)")
line()
status, log = call("GET", "/log")
for entry in log["entries"]:
    print(json.dumps(entry, indent=2, ensure_ascii=False))
    print("-" * 40)
