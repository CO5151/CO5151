"""Baselines for the Vietnamese Legal RAG evaluation (SBV-LawGraph benchmark).

Four retrieval paradigms are compared:

1. :class:`NaiveChunkRAG`          - top-k lexical/BM25 chunk lookup, no graph.
2. :class:`SBVLawGraphBaseline`    - top-k lookup + mechanical, unpruned 1-hop graph
   expansion (the SBV-LawGraph method, Phan et al., ACIIDS 2026).
3. :class:`ReActBaseline`          - iterative query-expansion loop over the corpus.
4. :class:`LegalPilotAgenticBaseline` - selective traversal with temporal pruning plus
   an external Claim Auditor verification pass.

Design contract
---------------
``predict(query, corpus)`` receives **only** the query and the retrieval corpus. Baseline
models never receive the evaluation ground truth; the evaluator keeps ground truth
strictly for scoring. This makes an oracle leak structurally impossible - an earlier
revision of this module read ``ground_truth[0]`` to build its own "retrieval", which
silently rigged every reported metric.

All figures produced here are *measured over the locally ingested corpus*. Because that
corpus only contains the instruments ingested locally (see
``src.evaluation.corpus.LegalCorpus``), absolute scores are not comparable to results
published over the full 1,703-document statutory corpus.
"""

from __future__ import annotations

import abc
import time
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.evaluation.metrics import normalize_article_id

if TYPE_CHECKING:
    from src.evaluation.corpus import CorpusChunk, LegalCorpus

#: Rough characters-per-token ratio used for context-size estimation.
#: This is an estimate, not a tokenizer measurement, and is reported as such.
_CHARS_PER_TOKEN = 4.0


@dataclass
class RetrievalPrediction:
    """Prediction output from a baseline model for evaluation."""

    query: str
    retrieved_articles: list[str]
    supported_claims: int = 0
    total_claims: int = 0
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def context_chars(self) -> int:
        """Character length of the retrieved context (used for token estimation)."""
        return sum(len(c) for c in self.retrieved_articles)


class BaseRetrievalModel(abc.ABC):
    """Abstract interface for benchmarked legal retrieval models."""

    def __init__(self, name: str) -> None:
        self.name = name

    @abc.abstractmethod
    def predict(self, query: str, corpus: LegalCorpus) -> RetrievalPrediction:
        """Execute retrieval for ``query`` against ``corpus``.

        Implementations MUST NOT receive or consult evaluation ground truth.

        Args:
            query: Legal question to answer.
            corpus: Indexed statutory corpus to retrieve from.

        Returns:
            A :class:`RetrievalPrediction` holding the ranked article ids.
        """
        raise NotImplementedError

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _clause_dict(chunk: CorpusChunk) -> dict:
        """Adapt a corpus chunk to the mapping shape expected by ClaimAuditorAgent."""
        return {
            "doc_id": chunk.doc_id,
            "status": chunk.status,
            "revoked_by": chunk.revoked_by,
            "article": chunk.article_id,
            "article_title": chunk.title,
            "content": chunk.text,
        }

    @classmethod
    def _audit(cls, chunks: list[CorpusChunk]) -> tuple[int, int]:
        """Run the real Claim Auditor over ``chunks`` and return (supported, total).

        Grounding is therefore *measured* by the same verification component used in
        production, rather than hardcoded per baseline.
        """
        if not chunks:
            return (0, 0)
        from src.agents.claim_auditor import ClaimAuditorAgent

        report = ClaimAuditorAgent().audit_provisions([cls._clause_dict(c) for c in chunks])
        return (report.grounded_claims, report.total_claims)

    @staticmethod
    def _estimate_tokens(chunks: list[CorpusChunk]) -> tuple[int, int]:
        """Estimate (input, output) tokens from retrieved context size.

        Input tokens are derived from the retrieved context length; output tokens are
        estimated from the number of retrieved provisions. Both are estimates.
        """
        context_chars = sum(len(c.text) for c in chunks)
        input_tokens = int(context_chars / _CHARS_PER_TOKEN)
        output_tokens = int(max(1, len(chunks)) * 120)
        return (input_tokens, output_tokens)

    def _finalize(
        self,
        query: str,
        chunks: list[CorpusChunk],
        start_time: float,
    ) -> RetrievalPrediction:
        """Assemble a prediction with measured latency and audited grounding."""
        supported, total = self._audit(chunks)
        input_tokens, output_tokens = self._estimate_tokens(chunks)
        return RetrievalPrediction(
            query=query,
            retrieved_articles=[c.article_id for c in chunks],
            supported_claims=supported,
            total_claims=total,
            latency_ms=round((time.perf_counter() - start_time) * 1000, 3),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


class NaiveChunkRAG(BaseRetrievalModel):
    """Baseline 1: top-k lexical chunk retrieval without any knowledge graph.

    Cannot follow amendment chains and performs no temporal verification, so revoked
    instruments remain in the context whenever they are lexically similar.
    """

    TOP_K = 5

    def __init__(self) -> None:
        super().__init__(name="Naive Chunk RAG")

    def predict(self, query: str, corpus: LegalCorpus) -> RetrievalPrediction:
        start = time.perf_counter()
        hits = corpus.search(query, k=self.TOP_K)
        return self._finalize(query, [chunk for chunk, _ in hits], start)


class SBVLawGraphBaseline(BaseRetrievalModel):
    """Baseline 2: static, unpruned 1-hop Graph-RAG (SBV-LawGraph method).

    Reproduces the mechanism described by Phan et al. (ACIIDS 2026): semantic top-k
    seeding followed by a *mechanical* 1-hop expansion over every outgoing relation.
    Because omnibus instruments cross-reference many unrelated provisions, this injects
    substantial distractor context and retains superseded instruments, since no
    temporal filter is applied.
    """

    SEED_K = 2
    MAX_CONTEXT = 5

    def __init__(self) -> None:
        super().__init__(name="Static 1-Hop SBV-LawGraph")

    def predict(self, query: str, corpus: LegalCorpus) -> RetrievalPrediction:
        start = time.perf_counter()
        seeds = [chunk for chunk, _ in corpus.search(query, k=self.SEED_K)]
        if not seeds:
            return self._finalize(query, [], start)

        expanded: list[CorpusChunk] = list(seeds)
        seen = {c.article_id for c in expanded}

        # Mechanical expansion: every chunk of every seed document, plus every
        # document reachable through its cross references - expired or not.
        for seed in seeds:
            for neighbour in corpus.neighbours(seed.doc_id):
                if neighbour.article_id not in seen:
                    expanded.append(neighbour)
                    seen.add(neighbour.article_id)
            for linked in corpus.linked_docs(seed.doc_id):
                for neighbour in corpus.chunks:
                    if neighbour.doc_id.lower() == linked and neighbour.article_id not in seen:
                        expanded.append(neighbour)
                        seen.add(neighbour.article_id)

        return self._finalize(query, expanded[: self.MAX_CONTEXT], start)


class ReActBaseline(BaseRetrievalModel):
    """Baseline 3: single-agent ReAct-style iterative retrieval.

    Alternates retrieve/observe steps, expanding the query with salient terms from the
    first pass. Improves recall over a single pass but performs no temporal validation,
    so revoked instruments can still surface.
    """

    MAX_CONTEXT = 4
    ITERATIONS = 2

    def __init__(self) -> None:
        super().__init__(name="Single-Agent ReAct")

    def predict(self, query: str, corpus: LegalCorpus) -> RetrievalPrediction:
        start = time.perf_counter()
        collected: list[CorpusChunk] = []
        seen: set[str] = set()
        current_query = query

        for _ in range(self.ITERATIONS):
            for chunk, _score in corpus.search(current_query, k=self.MAX_CONTEXT):
                if chunk.article_id not in seen:
                    collected.append(chunk)
                    seen.add(chunk.article_id)
            if not collected:
                break
            # "Observation" step: expand the query with frequent terms from what was
            # just retrieved.
            expansion = Counter(
                term for chunk in collected for term in set(chunk.tokens)
            ).most_common(6)
            extra = " ".join(term for term, _ in expansion)
            current_query = f"{query} {extra}".strip()

        return self._finalize(query, collected[: self.MAX_CONTEXT], start)


class LegalPilotAgenticBaseline(BaseRetrievalModel):
    """Baseline 4: LegalPilot-VN (this work).

    Employs:
    * selective edge traversal - the graph is walked only along edges that govern the
      query subject, instead of expanding every relation;
    * temporal pruning - chunks whose governing instrument is revoked are dropped
      *before* context assembly (``src.core.statute_status``);
    * an external Claim Auditor pass that verifies each retained provision and yields
      the per-claim grounding rate.
    """

    SEED_K = 3
    MAX_CONTEXT = 4

    def __init__(self) -> None:
        super().__init__(name="LegalPilot-VN Agentic (Ours)")

    def predict(self, query: str, corpus: LegalCorpus) -> RetrievalPrediction:
        start = time.perf_counter()
        seeds = [chunk for chunk, _ in corpus.search(query, k=self.SEED_K)]
        if not seeds:
            return self._finalize(query, [], start)

        # Selective traversal: re-route superseded seeds to their successor instrument
        # instead of dumping the whole neighbourhood, then drop anything not in force.
        selected: list[CorpusChunk] = []
        seen: set[str] = set()

        for seed in seeds:
            if seed.is_active:
                if seed.article_id not in seen:
                    selected.append(seed)
                    seen.add(seed.article_id)
                continue
            # Seed is revoked: follow the revocation chain, if the successor is ingested.
            for chunk in corpus.chunks:
                if chunk.article_id in seen or not chunk.is_active:
                    continue
                if seed.revoked_by and _same_instrument(chunk.doc_id, seed.revoked_by):
                    selected.append(chunk)
                    seen.add(chunk.article_id)

        # Backfill with remaining active chunks ranked by the query, so the context is
        # not truncated when pruning removes most candidates.
        if len(selected) < self.MAX_CONTEXT:
            for chunk, _score in corpus.search(query, k=len(corpus.chunks)):
                if len(selected) >= self.MAX_CONTEXT:
                    break
                if chunk.is_active and chunk.article_id not in seen:
                    selected.append(chunk)
                    seen.add(chunk.article_id)

        return self._finalize(query, selected[: self.MAX_CONTEXT], start)


def _same_instrument(doc_id: str, other: str) -> bool:
    """Compare document numbers ignoring formatting and accents.

    Args:
        doc_id: First document number, e.g. ``"52/2024/ND-CP"``.
        other: Second document number, possibly normalized differently.

    Returns:
        ``True`` when both refer to the same instrument.
    """
    left = normalize_article_id(doc_id)
    right = normalize_article_id(other)
    return bool(left) and (left == right or left in right or right in left)
