r"""Evaluation Metrics strictly adhering to the SBV-LawGraph paper.

Reference:
K. N. Phan, X.-B. Le, T. T. Quan, "SBV-LawGraph: A Hybrid RAG Approach Integrating
Knowledge Graph for Legal Documents," Proc. ACIIDS 2026, Springer.

Formulations implemented:
- Precision@k: |retrieved[:k] ∩ ground_truth| / k
- Recall@k:    |retrieved[:k] ∩ ground_truth| / |ground_truth|
- F1@k:        2 * (P@k * R@k) / (P@k + R@k)
- F2@k:        5 * (P@k * R@k) / (4 * P@k + R@k)  [Emphasizes recall for high-stakes legal search]
- Hit@k:       1.0 if any ground_truth in retrieved[:k] else 0.0
- MRR:         1 / rank of first relevant provision
- Noise Ratio: |retrieved \ ground_truth| / |retrieved| [Measures context dilution / distraction]
- Grounding Rate: supported_claims / total_claims [Temporal validity & SAFE faithfulness]
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass


def normalize_article_id(art_id: str) -> str:
    """Normalizes legal article identifiers for exact/canonical matching.

    Examples:
        '12/2022/TT-NHNN_15' -> '12/2022/tt-nhnn_15'
        'Điều 15 Thông tư 12/2022/TT-NHNN' -> '12/2022/tt-nhnn_15'
        '52/2024/ND-CP:Điều 22' -> '52/2024/nd-cp_22'
    """
    if not art_id:
        return ""

    s = art_id.strip().lower()

    # Match patterns like 'Điều 15 Thông tư 12/2022/TT-NHNN'
    m1 = re.search(r"điều\s+(\d+)\s+.*?(thông tư|nghị định|luật)?\s*([0-9]+/[0-9]+/[a-z0-9\-]+)", s)
    if m1:
        art_num = m1.group(1)
        doc_code = m1.group(3)
        return f"{doc_code}_{art_num}"

    # Match '52/2024/nd-cp:điều 22' or '52/2024/nd-cp_22'
    s = s.replace("điều ", "").replace("dieu ", "").replace(":", "_").replace(" ", "")
    # Remove leading dots or underscores
    s = s.strip("._-")
    return s


def precision_at_k(retrieved: list[str], ground_truth: list[str], k: int = 2) -> float:
    """Calculates Precision@k.

    Precision@k = |retrieved[:k] ∩ ground_truth| / k
    """
    if k <= 0:
        return 0.0
    if not retrieved:
        return 0.0

    ret_k = [normalize_article_id(x) for x in retrieved[:k]]
    gt_set = {normalize_article_id(x) for x in ground_truth}

    hits = sum(1 for item in ret_k if item in gt_set)
    return round(hits / k, 4)


def recall_at_k(retrieved: list[str], ground_truth: list[str], k: int = 2) -> float:
    """Calculates Recall@k.

    Recall@k = |retrieved[:k] ∩ ground_truth| / |ground_truth|
    """
    if not ground_truth:
        return 1.0  # Perfect recall if no relevant items required
    if not retrieved or k <= 0:
        return 0.0

    ret_k = {normalize_article_id(x) for x in retrieved[:k]}
    gt_set = {normalize_article_id(x) for x in ground_truth}

    hits = len(ret_k.intersection(gt_set))
    return round(hits / len(gt_set), 4)


def f1_at_k(retrieved: list[str], ground_truth: list[str], k: int = 2) -> float:
    """Calculates harmonic F1 score at rank k."""
    p = precision_at_k(retrieved, ground_truth, k)
    r = recall_at_k(retrieved, ground_truth, k)
    if p + r == 0:
        return 0.0
    return round(2 * (p * r) / (p + r), 4)


def f2_at_k(retrieved: list[str], ground_truth: list[str], k: int = 2) -> float:
    """Calculates F2 score at rank k (weighting recall twice as heavily as precision).

    Standard for high-consequence compliance systems (R5 in proposal).
    """
    p = precision_at_k(retrieved, ground_truth, k)
    r = recall_at_k(retrieved, ground_truth, k)
    if (4 * p + r) == 0:
        return 0.0
    return round(5 * (p * r) / (4 * p + r), 4)


def hit_at_k(retrieved: list[str], ground_truth: list[str], k: int = 2) -> float:
    """Calculates Hit Rate@k (1.0 if any ground_truth item is in top-k, else 0.0)."""
    if not ground_truth:
        return 1.0
    if not retrieved or k <= 0:
        return 0.0

    ret_k = {normalize_article_id(x) for x in retrieved[:k]}
    gt_set = {normalize_article_id(x) for x in ground_truth}

    return 1.0 if bool(ret_k.intersection(gt_set)) else 0.0


def mean_reciprocal_rank(retrieved: list[str], ground_truth: list[str]) -> float:
    """Calculates Mean Reciprocal Rank (MRR) for the first relevant article."""
    if not ground_truth or not retrieved:
        return 0.0

    gt_set = {normalize_article_id(x) for x in ground_truth}
    for rank, item in enumerate(retrieved, start=1):
        if normalize_article_id(item) in gt_set:
            return round(1.0 / rank, 4)
    return 0.0


def noise_ratio(retrieved: list[str], ground_truth: list[str]) -> float:
    r"""Calculates Noise Ratio (context dilution / prompt pollution).

    Noise Ratio = |retrieved \ ground_truth| / |retrieved|
    In SBV-LawGraph, static 1-hop expansion had >60% distracting noise.
    """
    if not retrieved:
        return 0.0

    ret_set = {normalize_article_id(x) for x in retrieved}
    gt_set = {normalize_article_id(x) for x in ground_truth}

    noise_count = len(ret_set - gt_set)
    return round(noise_count / len(ret_set), 4)


def grounding_rate(supported_claims: int, total_claims: int) -> float:
    """Calculates Per-Claim Grounding Rate (SAFE / Ragas Faithfulness)."""
    if total_claims <= 0:
        return 1.0
    return round(supported_claims / total_claims, 4)


@dataclass
class MetricSummary:
    """Aggregated evaluation metrics for a model or baseline."""

    model_name: str
    precision_at_2: float
    precision_at_5: float
    recall_at_2: float
    recall_at_5: float
    f1_at_2: float
    f2_at_2: float
    hit_at_2: float
    hit_at_5: float
    mrr: float
    noise_ratio: float
    grounding_rate: float
    avg_latency_ms: float
    est_cost_usd_per_query: float

    def to_dict(self) -> dict:
        return asdict(self)
