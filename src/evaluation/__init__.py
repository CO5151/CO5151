"""Evaluation Module for LegalPilot-VN (Theme 9).

Implements the evaluation methodology and metrics from the SBV-LawGraph paper:
K. N. Phan, X.-B. Le, T. T. Quan, "SBV-LawGraph: A Hybrid RAG Approach Integrating
Knowledge Graph for Legal Documents," Proc. ACIIDS 2026, Springer.

Exports:
- precision_at_k, recall_at_k, f1_at_k, f2_at_k, hit_at_k, mean_reciprocal_rank
- noise_ratio, grounding_rate, normalize_article_id, MetricSummary
- NaiveChunkRAG, SBVLawGraphBaseline, ReActBaseline, LegalPilotAgenticBaseline
- SBVLawGraphEvaluator
- generate_markdown_report, generate_latex_table
"""

from src.evaluation.baselines import (
    BaseRetrievalModel,
    LegalPilotAgenticBaseline,
    NaiveChunkRAG,
    ReActBaseline,
    RetrievalPrediction,
    SBVLawGraphBaseline,
)
from src.evaluation.evaluator import SBVLawGraphEvaluator
from src.evaluation.metrics import (
    MetricSummary,
    f1_at_k,
    f2_at_k,
    grounding_rate,
    hit_at_k,
    mean_reciprocal_rank,
    noise_ratio,
    normalize_article_id,
    precision_at_k,
    recall_at_k,
)
from src.evaluation.report import generate_latex_table, generate_markdown_report

__all__ = [
    "precision_at_k",
    "recall_at_k",
    "f1_at_k",
    "f2_at_k",
    "hit_at_k",
    "mean_reciprocal_rank",
    "noise_ratio",
    "grounding_rate",
    "normalize_article_id",
    "MetricSummary",
    "BaseRetrievalModel",
    "RetrievalPrediction",
    "NaiveChunkRAG",
    "SBVLawGraphBaseline",
    "ReActBaseline",
    "LegalPilotAgenticBaseline",
    "SBVLawGraphEvaluator",
    "generate_markdown_report",
    "generate_latex_table",
]
