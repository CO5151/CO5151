"""Local statutory retrieval corpus for the LegalPilot-VN evaluation suite.

This module builds a *real* retrieval corpus from the artifacts that are actually
present in the repository, so that baseline models can perform genuine,
query-driven retrieval without ever seeing the evaluation ground truth.

Sources, in order of preference:

1. ``data/processed/qdrant_chunks_export.json`` — article/clause chunks produced by
   ``src.knowledge.ingestion`` when a live Qdrant instance is unavailable.
2. ``data/processed/neo4j_graph_export.json`` — document metadata (status, revocation
   chain, cross references) written by the same offline fallback.

The corpus is intentionally small: it contains only the instruments that have been
ingested locally. Metrics computed against it are therefore *measured but partial* —
they must never be presented as results over the full 1,703-document statutory corpus.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from src.core.logger import logger
from src.core.statute_status import is_active_status

DEFAULT_CHUNK_PATH = "data/processed/qdrant_chunks_export.json"
DEFAULT_GRAPH_PATH = "data/processed/neo4j_graph_export.json"

_TOKEN_RE = re.compile(r"[0-9a-zà-ỹđ/+-]+", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    """Tokenize Vietnamese legal text into lowercase, diacritic-folded terms.

    Diacritics are stripped so that ``"ví điện tử"`` and ``"vi dien tu"`` match,
    which makes retrieval robust to the inconsistent accent usage found in the
    benchmark question set.

    Args:
        text: Raw text to tokenize.

    Returns:
        List of normalized tokens.
    """
    if not text:
        return []
    decomposed = unicodedata.normalize("NFD", text.lower())
    folded = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    # 'đ' does not decompose under NFD, so normalize it explicitly.
    folded = folded.replace("đ", "d")
    return [t for t in _TOKEN_RE.findall(folded) if len(t) > 0]


@dataclass
class CorpusChunk:
    """A single retrievable statutory chunk (one article or clause)."""

    article_id: str
    doc_id: str
    text: str
    title: str = ""
    status: str = "unknown"
    revoked_by: str | None = None
    cross_references: list[dict] = field(default_factory=list)
    tokens: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.tokens:
            self.tokens = tokenize(f"{self.title} {self.text}")

    @property
    def is_active(self) -> bool:
        """Whether the governing document is currently in force."""
        return is_active_status(self.status, self.revoked_by)


class LegalCorpus:
    """BM25-indexed statutory corpus assembled from local ingestion artifacts."""

    def __init__(self, chunks: list[CorpusChunk]) -> None:
        self.chunks = chunks
        self._doc_freq: Counter[str] = Counter()
        for c in chunks:
            for term in set(c.tokens):
                self._doc_freq[term] += 1
        self._avg_len = (sum(len(c.tokens) for c in chunks) / len(chunks)) if chunks else 0.0
        # BM25 hyper-parameters (standard defaults)
        self.k1 = 1.5
        self.b = 0.75

    # -- construction ---------------------------------------------------------

    @classmethod
    def from_processed_artifacts(
        cls,
        chunk_path: str | Path = DEFAULT_CHUNK_PATH,
        graph_path: str | Path = DEFAULT_GRAPH_PATH,
    ) -> LegalCorpus:
        """Build a corpus from the offline ingestion exports.

        Returns an empty corpus (rather than raising) when the artifacts are
        absent, so that callers can report "no corpus available" instead of
        fabricating results.
        """
        doc_meta: dict[str, dict] = {}
        graph_file = Path(graph_path)
        if graph_file.exists():
            try:
                raw_docs = json.loads(graph_file.read_text(encoding="utf-8"))
                for doc_id, doc in raw_docs.items():
                    doc_meta[str(doc_id).lower()] = doc
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Could not read graph export %s: %s", graph_file, exc)

        chunks: list[CorpusChunk] = []
        chunk_file = Path(chunk_path)
        if chunk_file.exists():
            try:
                raw_chunks = json.loads(chunk_file.read_text(encoding="utf-8"))
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Could not read chunk export %s: %s", chunk_file, exc)
                raw_chunks = []

            for entry in raw_chunks:
                payload = entry.get("payload") or {}
                doc_id = str(payload.get("doc_id", "")).strip()
                if not doc_id:
                    continue
                article_number = str(payload.get("article_number", "")).strip()
                # Canonical form matching the benchmark ground-truth convention,
                # e.g. "40/2024/TT-NHNN" + "18" -> "40/2024/tt-nhnn_18".
                article_id = (
                    f"{doc_id.lower()}_{article_number}"
                    if article_number
                    else str(payload.get("article_id", doc_id)).lower()
                )
                meta = doc_meta.get(doc_id.lower(), {})
                chunks.append(
                    CorpusChunk(
                        article_id=article_id,
                        doc_id=doc_id,
                        text=str(entry.get("text", "")),
                        title=str(payload.get("title", "")),
                        status=str(meta.get("status", payload.get("status", "unknown"))),
                        revoked_by=meta.get("revoked_by"),
                        cross_references=list(meta.get("cross_references") or []),
                    )
                )

        logger.info("LegalCorpus built with %d chunk(s)", len(chunks))
        return cls(chunks)

    # -- retrieval ------------------------------------------------------------

    def _idf(self, term: str) -> float:
        n = len(self.chunks)
        df = self._doc_freq.get(term, 0)
        # BM25 probabilistic idf with +1 smoothing to stay non-negative
        return math.log(1.0 + (n - df + 0.5) / (df + 0.5))

    def search(self, query: str, k: int = 5) -> list[tuple[CorpusChunk, float]]:
        """Rank chunks against ``query`` using Okapi BM25.

        Args:
            query: Natural-language legal question.
            k: Maximum number of chunks to return.

        Returns:
            List of ``(chunk, score)`` pairs sorted by descending score. Only
            chunks with a strictly positive score are returned.
        """
        q_terms = tokenize(query)
        if not q_terms or not self.chunks:
            return []

        scored: list[tuple[CorpusChunk, float]] = []
        for chunk in self.chunks:
            tf = Counter(chunk.tokens)
            length = len(chunk.tokens) or 1
            score = 0.0
            for term in q_terms:
                freq = tf.get(term, 0)
                if not freq:
                    continue
                denom = freq + self.k1 * (1 - self.b + self.b * length / (self._avg_len or 1))
                score += self._idf(term) * (freq * (self.k1 + 1)) / denom
            if score > 0:
                scored.append((chunk, score))

        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:k]

    def neighbours(self, doc_id: str) -> list[CorpusChunk]:
        """Return every chunk belonging to ``doc_id`` (mechanical 1-hop expansion)."""
        return [c for c in self.chunks if c.doc_id.lower() == doc_id.lower()]

    def linked_docs(self, doc_id: str) -> list[str]:
        """Return document ids reachable from ``doc_id`` via cross references.

        This models unpruned graph expansion: edges are followed regardless of
        whether the target instrument is still in force.
        """
        targets: list[str] = []
        for chunk in self.neighbours(doc_id):
            for ref in chunk.cross_references:
                target = str(ref.get("target_doc_id", "")).strip()
                if target:
                    targets.append(target.lower())
        return targets

    @property
    def is_empty(self) -> bool:
        """Whether the corpus contains no retrievable chunks."""
        return not self.chunks
