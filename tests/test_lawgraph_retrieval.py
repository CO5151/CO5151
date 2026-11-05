"""Unit tests for LawGraphAgent dense / lexical retrieval routing (no live services)."""

from typing import Any

import pytest

from src.agents import lawgraph
from src.agents.lawgraph import LawGraphAgent, _fuse_ranked


class _FakeEmbedder:
    def encode(self, text: str, normalize_embeddings: bool = True) -> list[float]:
        return [0.1, 0.2, 0.3]


class _FakeQdrant:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[dict[str, Any]] = []

    def search(self, vector: list[float], limit: int, status_filter: str | None) -> list[Any]:
        self.calls.append({"limit": limit, "status_filter": status_filter})
        return self.rows[:limit]


def _point(doc_id: str, article: str, clause: str, score: float, status: str) -> dict[str, Any]:
    return {
        "score": score,
        "payload": {
            "doc_id": doc_id,
            "article_id": f"{doc_id}:Article_{article}",
            "article_number": article,
            "clause_number": clause,
            "title": f"Văn bản {doc_id}",
            "status": status,
            "text": f"[{doc_id}] Điều {article} khoản {clause}",
        },
    }


@pytest.fixture
def fake_dense(monkeypatch: pytest.MonkeyPatch) -> _FakeQdrant:
    rows = [
        _point("39/2014/TT-NHNN", "8", "1", 0.95, "expired"),
        _point("40/2024/TT-NHNN", "8", "1", 0.93, "in_force"),
        _point("40/2024/TT-NHNN", "8", "2", 0.92, "in_force"),
        _point("52/2024/ND-CP", "13", "1", 0.90, "in_force"),
    ]
    qdrant = _FakeQdrant(rows)
    monkeypatch.setattr(lawgraph, "_QDRANT_HANDLE", {"manager": qdrant})
    monkeypatch.setattr(lawgraph, "_EMBEDDER", {"model": _FakeEmbedder()})
    monkeypatch.setattr(
        lawgraph,
        "_GRAPH_STATUS",
        {"39/2014/TT-NHNN": {"status": "expired", "revoked_by": "40/2024/TT-NHNN"}},
    )
    return qdrant


def test_fuse_ranked_puts_in_force_first_and_keeps_expired_last():
    expired = {"doc_id": "A", "article": "Điều 1", "status": "expired"}
    active = {"doc_id": "B", "article": "Điều 1", "status": "in_force"}
    fused = _fuse_ranked([[expired, active]], limit=5)
    assert [i["doc_id"] for i in fused] == ["B", "A"]
    assert all("fused_score" in i for i in fused)


def test_fuse_ranked_rewards_agreement_between_retrievers():
    a = {"doc_id": "A", "article_id": "A:Article_1", "status": "in_force"}
    b = {"doc_id": "B", "article_id": "B:Article_1", "status": "in_force"}
    c = {"doc_id": "C", "article_id": "C:Article_1", "status": "in_force"}
    fused = _fuse_ranked([[a, b], [c, b]], limit=3)
    assert fused[0]["doc_id"] == "B"


def test_qdrant_retrieve_collapses_clauses_and_trusts_graph_status(fake_dense: _FakeQdrant):
    hits = LawGraphAgent().qdrant_retrieve("ví điện tử", top_k=5)

    assert [h["article_id"] for h in hits] == [
        "39/2014/TT-NHNN:Article_8",
        "40/2024/TT-NHNN:Article_8",
        "52/2024/ND-CP:Article_13",
    ]
    assert hits[0]["revoked_by"] == "40/2024/TT-NHNN"
    assert fake_dense.calls[0] == {"limit": 20, "status_filter": None}


def test_default_retrieval_is_dense_in_force_first_without_lexical(
    fake_dense: _FakeQdrant, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("BENCH_RETRIEVER", raising=False)
    agent = LawGraphAgent()
    lexical_calls: list[Any] = []

    def record_lexical(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        lexical_calls.append(args)
        return []

    monkeypatch.setattr(agent, "neo4j_retrieve", record_lexical)

    results = agent.retrieve_provisions(["ví điện tử"], ["ví"], query="ví điện tử", dense_top_k=2)

    assert [r["doc_id"] for r in results] == ["40/2024/TT-NHNN", "52/2024/ND-CP"]
    assert lexical_calls == []
    assert fake_dense.calls[0]["limit"] == 16  # (2 * 2 over-fetch) * 4 clauses per article


def test_default_retrieval_falls_back_to_lexical_when_qdrant_is_empty(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("BENCH_RETRIEVER", raising=False)
    agent = LawGraphAgent()
    lexical_hit = {"doc_id": "12/2022/TT-NHNN", "article": "Điều 3", "status": "in_force"}
    monkeypatch.setattr(agent, "neo4j_retrieve", lambda *a, **k: [lexical_hit])

    results = agent.retrieve_provisions(["vay nước ngoài"], ["vay"], query="vay nước ngoài")
    assert results[0]["doc_id"] == "12/2022/TT-NHNN"


def test_bench_retriever_neo4j_skips_dense(
    fake_dense: _FakeQdrant, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("BENCH_RETRIEVER", "neo4j")
    agent = LawGraphAgent()
    monkeypatch.setattr(agent, "neo4j_retrieve", lambda *a, **k: [])
    agent.retrieve_provisions(["x"], ["x"], query="x")
    assert fake_dense.calls == []
