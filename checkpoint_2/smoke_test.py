"""Headless smoke test --- proves the ADK graph runs before opening the web UI.

Usage (from CO5151/checkpoint_2/):

    ../.venv-adk/bin/python smoke_test.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Force the dense retriever so the demo does not depend on Neo4j being up.
os.environ.setdefault("BENCH_RETRIEVER", "dense")

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from legalpilot_web.agent import root_agent  # noqa: E402

# Câu demo ngắn: planner sinh subgoal dạng cụm danh từ, dense retrieval bắt
# đúng 52/2024/ND-CP Điều 22 (mức vốn 50 tỷ). Câu hỏi dài dạng "Doanh nghiệp
# muốn xin cấp phép ... căn cứ theo văn bản nào?" làm subgoal thành câu hỏi và
# hay trả về "Không đủ căn cứ".
QUERY = "Vốn điều lệ tối thiểu để cấp phép dịch vụ ví điện tử là bao nhiêu?"


async def main() -> None:
    runner = InMemoryRunner(agent=root_agent, app_name="legalpilot_web")
    session = await runner.session_service.create_session(
        app_name="legalpilot_web", user_id="demo", state={}
    )

    print(f"\n=== QUERY ===\n{QUERY}\n")
    print("=== EVENT TRACE ===")

    seen: list[str] = []
    async for event in runner.run_async(
        user_id="demo",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part.from_text(text=QUERY)]),
    ):
        author = getattr(event, "author", "?")
        seen.append(author)
        state_keys = sorted((event.actions.state_delta or {}).keys()) if event.actions else []
        text = ""
        if event.content and event.content.parts:
            text = "".join(p.text or "" for p in event.content.parts).strip()
        line = f"  [{author}]"
        if state_keys:
            line += f" state+={state_keys}"
        print(line)
        if text:
            print(f"      {text[:400]}{'...' if len(text) > 400 else ''}")

    final = await runner.session_service.get_session(
        app_name="legalpilot_web", user_id="demo", session_id=session.id
    )
    state = dict(final.state)

    print("\n=== AGENTS INVOKED ===")
    print(" -> ".join(seen))

    print("\n=== FINAL STATE KEYS ===")
    print(sorted(state.keys()))

    print("\n=== DANH SÁCH ĐIỀU KHOẢN SAU AUDIT ===")
    for c in state.get("retrieved_clauses", []):
        print(f"  {c.get('doc_id')} {c.get('article')} | revoked_by={c.get('revoked_by')}")

    print("\n=== AUDIT SUMMARY ===")
    print(state.get("audit_summary"))

    print("\n=== FINAL DOSSIER ===")
    print(state.get("final_dossier"))


if __name__ == "__main__":
    asyncio.run(main())
