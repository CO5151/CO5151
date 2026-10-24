"""Tim cau hoi demo bat duoc vong recovery (Audit -> Recovery -> Audit) on dinh.

Chay: /Users/tungdl/Documents/CO5151/.venv-adk/bin/python find_loop_query.py
"""

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path("/Users/tungdl/Documents/CO5151/CO5151")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "checkpoint_2"))
os.environ["BENCH_RETRIEVER"] = "dense"

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from legalpilot_web.agent import root_agent  # noqa: E402

CANDIDATES = [
    "Điều kiện cung ứng dịch vụ trung gian thanh toán gồm những gì?",
    "Điều kiện để được cung ứng dịch vụ trung gian thanh toán?",
    "Tổ chức cung ứng dịch vụ trung gian thanh toán phải đáp ứng điều kiện gì?",
    "Vốn điều lệ tối thiểu khi cung ứng dịch vụ trung gian thanh toán?",
]


async def one(q: str) -> tuple[list[str], list[str]]:
    runner = InMemoryRunner(agent=root_agent, app_name="probe")
    sess = await runner.session_service.create_session(app_name="probe", user_id="u", state={})
    order: list[str] = []
    async for ev in runner.run_async(
        user_id="u",
        session_id=sess.id,
        new_message=types.Content(role="user", parts=[types.Part.from_text(text=q)]),
    ):
        order.append(getattr(ev, "author", "?"))
    final = await runner.session_service.get_session(app_name="probe", user_id="u", session_id=sess.id)
    docs = [c["doc_id"] for c in dict(final.state).get("retrieved_clauses", [])]
    return order, docs


async def main() -> None:
    for q in CANDIDATES:
        for attempt in (1, 2):
            order, docs = await one(q)
            fired = "RecoveryWorker" in order
            print(f"{'FIRED' if fired else '  no '}  trial{attempt}  {q[:52]}")
            print(f"        docs={sorted(set(docs))}")
            print(f"        trace={' -> '.join(order)}")


asyncio.run(main())
