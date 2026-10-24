"""Chay 1 cau hoi qua ADK Web API (port 8765) va in event trace.

Chung minh backend cua `adk web` phuc vu dung agent, khong chi load trang.
"""

from __future__ import annotations

import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8765"
# Ten app phu thuoc vao thu muc chay `adk web`:
#   chay trong checkpoint_2/            -> "legalpilot_web"
#   chay o thu muc cha (CO5151/)        -> "CO5151.checkpoint_2.legalpilot_web"
# Tu dong chon app nao chua "legalpilot_web".
with urllib.request.urlopen(f"{BASE}/list-apps", timeout=10) as _r:
    _apps = json.load(_r)
APP = next((a for a in _apps if "legalpilot_web" in a), _apps[0]) if _apps else "legalpilot_web"
USER = "demo"
SESSION = "sess_demo_01"
QUERY = "Vốn điều lệ tối thiểu để cấp phép dịch vụ ví điện tử là bao nhiêu?"


def post(path: str, payload: dict) -> bytes:
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


# 1. tao session
try:
    post(f"/apps/{APP}/users/{USER}/sessions", {"session_id": SESSION, "state": {}})
    print(f"session {SESSION} created")
except Exception as e:  # noqa: BLE001
    print(f"session: {e} (co the da ton tai)")

# 2. chay agent, doc SSE
req = urllib.request.Request(
    f"{BASE}/run_sse",
    data=json.dumps(
        {
            "app_name": APP,
            "user_id": USER,
            "session_id": SESSION,
            "new_message": {"role": "user", "parts": [{"text": QUERY}]},
        }
    ).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)

print(f"\nQUERY: {QUERY}\n\nEVENT TRACE:")
order: list[str] = []
with urllib.request.urlopen(req, timeout=180) as resp:
    for raw in resp:
        line = raw.decode("utf-8", "replace").strip()
        if not line.startswith("data:"):
            continue
        try:
            ev = json.loads(line[5:].strip())
        except json.JSONDecodeError:
            continue
        author = ev.get("author", "?")
        order.append(author)
        delta = list((ev.get("actions") or {}).get("stateDelta", {}).keys())
        parts = (ev.get("content") or {}).get("parts") or []
        text = " ".join(p.get("text", "") for p in parts if p.get("text")).strip()
        print(f"  [{author}]" + (f" state+={delta}" if delta else ""))
        if text:
            print(f"      {text[:200]}")

print("\nAGENTS:", " -> ".join(order))

# 3. doc state cuoi cung qua REST
url = f"{BASE}/apps/{APP}/users/{USER}/sessions/{SESSION}"
with urllib.request.urlopen(url, timeout=30) as r:
    sess = json.load(r)
state = sess.get("state", {})
print("\nFINAL DOSSIER:")
print(state.get("final_dossier", "<trong>"))

sys.exit(0)
