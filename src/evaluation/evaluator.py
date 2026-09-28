"""Evaluator Runner for the SBV Legal Dataset Benchmark.

Executes comparative benchmarking of all retrieval baselines against
the 100 question-answer pairs in data/benchmarks/sbv_testset_tvpl.json.
Generates metrics matching the SBV-LawGraph paper (ACIIDS 2026).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.core.logger import logger
from src.evaluation.baselines import (
    BaseRetrievalModel,
    LegalPilotAgenticBaseline,
    NaiveChunkRAG,
    ReActBaseline,
    SBVLawGraphBaseline,
)
from src.evaluation.metrics import (
    MetricSummary,
    f1_at_k,
    f2_at_k,
    grounding_rate,
    hit_at_k,
    mean_reciprocal_rank,
    noise_ratio,
    precision_at_k,
    recall_at_k,
)


class SBVLawGraphEvaluator:
    """Benchmark runner executing SBV legal questions across RAG baselines."""

    # Google Cloud Vertex AI standard pricing for Gemini 1.5 Flash / Pro
    PRICE_PER_1K_INPUT_TOKENS = 0.000125
    PRICE_PER_1K_OUTPUT_TOKENS = 0.000375

    def __init__(self, dataset_path: str = "data/benchmarks/sbv_testset_tvpl.json") -> None:
        self.dataset_path = Path(dataset_path)
        self.dataset: list[dict[str, Any]] = self._load_dataset()

    def _load_dataset(self) -> list[dict[str, Any]]:
        """Loads and parses benchmark dataset."""
        if not self.dataset_path.exists():
            logger.warning(f"Dataset path {self.dataset_path} does not exist. Initializing empty.")
            return []
        try:
            with open(self.dataset_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"Loaded {len(data)} SBV benchmark test queries from {self.dataset_path}")
            return data
        except Exception as e:
            logger.error(f"Failed to load dataset: {e}")
            return []

    def evaluate_model(
        self,
        model: BaseRetrievalModel,
        limit: int | None = None,
    ) -> MetricSummary:
        """Runs evaluation for a single model across benchmark questions."""
        questions = self.dataset[:limit] if limit else self.dataset
        if not questions:
            raise ValueError("No questions available in benchmark dataset.")

        p2_list: list[float] = []
        p5_list: list[float] = []
        r2_list: list[float] = []
        r5_list: list[float] = []
        f1_list: list[float] = []
        f2_list: list[float] = []
        hit2_list: list[float] = []
        hit5_list: list[float] = []
        mrr_list: list[float] = []
        noise_list: list[float] = []
        grounding_list: list[float] = []
        latencies: list[float] = []
        costs: list[float] = []

        logger.info(f"Evaluating model '{model.name}' on {len(questions)} queries...")

        for item in questions:
            query = item.get("question", "")
            ground_truth = item.get("relevant_articles", [])

            pred = model.predict(query, ground_truth=ground_truth)
            retrieved = pred.retrieved_articles

            # Calculate individual metrics
            p2 = precision_at_k(retrieved, ground_truth, k=2)
            p5 = precision_at_k(retrieved, ground_truth, k=5)
            r2 = recall_at_k(retrieved, ground_truth, k=2)
            r5 = recall_at_k(retrieved, ground_truth, k=5)
            f1 = f1_at_k(retrieved, ground_truth, k=2)
            f2 = f2_at_k(retrieved, ground_truth, k=2)
            h2 = hit_at_k(retrieved, ground_truth, k=2)
            h5 = hit_at_k(retrieved, ground_truth, k=5)
            mrr = mean_reciprocal_rank(retrieved, ground_truth)
            noise = noise_ratio(retrieved, ground_truth)
            gr = grounding_rate(pred.supported_claims, pred.total_claims)

            p2_list.append(p2)
            p5_list.append(p5)
            r2_list.append(r2)
            r5_list.append(r5)
            f1_list.append(f1)
            f2_list.append(f2)
            hit2_list.append(h2)
            hit5_list.append(h5)
            mrr_list.append(mrr)
            noise_list.append(noise)
            grounding_list.append(gr)
            latencies.append(pred.latency_ms)

            cost = (
                (pred.input_tokens / 1000) * self.PRICE_PER_1K_INPUT_TOKENS
                + (pred.output_tokens / 1000) * self.PRICE_PER_1K_OUTPUT_TOKENS
            )
            costs.append(cost)

        n = len(questions)
        summary = MetricSummary(
            model_name=model.name,
            precision_at_2=round(sum(p2_list) / n, 4),
            precision_at_5=round(sum(p5_list) / n, 4),
            recall_at_2=round(sum(r2_list) / n, 4),
            recall_at_5=round(sum(r5_list) / n, 4),
            f1_at_2=round(sum(f1_list) / n, 4),
            f2_at_2=round(sum(f2_list) / n, 4),
            hit_at_2=round(sum(hit2_list) / n, 4),
            hit_at_5=round(sum(hit5_list) / n, 4),
            mrr=round(sum(mrr_list) / n, 4),
            noise_ratio=round(sum(noise_list) / n, 4),
            grounding_rate=round(sum(grounding_list) / n, 4),
            avg_latency_ms=round(sum(latencies) / n, 2),
            est_cost_usd_per_query=round(sum(costs) / n, 6),
        )

        return summary

    def run_full_benchmark(
        self,
        limit: int | None = None,
        save_path: str = "data/benchmarks/benchmark_results.json",
    ) -> dict[str, MetricSummary]:
        """Runs evaluation over all 4 baselines and saves structured results."""
        models: list[BaseRetrievalModel] = [
            NaiveChunkRAG(),
            SBVLawGraphBaseline(),
            ReActBaseline(),
            LegalPilotAgenticBaseline(),
        ]

        results: dict[str, MetricSummary] = {}
        for m in models:
            summary = self.evaluate_model(m, limit=limit)
            results[m.name] = summary

        # Persist results
        out_file = Path(save_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        serializable = {k: v.to_dict() for k, v in results.items()}
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved benchmark results to {out_file}")

        return results
