#!/usr/bin/env python3
"""Tiny web front-end for the action-boundary demo (stdlib only).

    python serve_demo.py            # then open http://localhost:8765
    python serve_demo.py --port 9000

The server is deliberately dumb: every decision comes from action_gateway.py,
so what you see in the browser is the same code that run_demo.py prints.
"""

from __future__ import annotations

import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from action_gateway import Gateway, Request, payload_hash

ROOT = Path(__file__).parent
WEB = ROOT / "web"

GW = Gateway()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(WEB), **kw)

    # -- helpers ---------------------------------------------------------
    def _json(self, obj, code: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def log_message(self, fmt, *args):  # quieter console
        return

    # -- routes ----------------------------------------------------------
    def do_POST(self):
        try:
            data = self._read()
        except json.JSONDecodeError as exc:
            return self._json({"error": f"invalid JSON: {exc}"}, 400)

        if self.path == "/api/decide":
            return self._decide(data)
        if self.path == "/api/approve":
            token = GW.issue_approval(
                data.get("tool", ""), data.get("args", {}) or {}
            )
            return self._json({"token": token})
        if self.path == "/api/reset":
            GW.reset()
            return self._json({"ok": True})
        return self._json({"error": "not found"}, 404)

    def _decide(self, data):
        req = Request(
            agent=data.get("agent", ""),
            tool=data.get("tool", ""),
            args=data.get("args", {}) or {},
            origin=data.get("origin") or ["user"],
            approval_token=data.get("approval_token") or None,
            idempotency_key=data.get("idempotency_key") or None,
        )
        if data.get("mode") == "prompt":
            dec = GW.decide_prompt_only(req)
        else:
            dec = GW.decide(req)
        out = dec.as_dict()
        out["args_hash"] = payload_hash(req.tool, req.args)
        out["audit"] = GW.audit[-6:]
        return self._json(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"S2-5 demo  ->  http://{args.host}:{args.port}   (Ctrl-C để dừng)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
