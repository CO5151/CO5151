"""Evaluator Runner for the SBV Legal Dataset Benchmark.

Executes comparative benchmarking of all retrieval baselines against
the 100 question-answer pairs in data/benchmarks/sbv_testset_tvpl.json.
Generates metrics matching the SBV-LawGraph paper (ACIIDS 2026).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar, cast

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

    # Pricing reference table ($ per 1,000 tokens)
    PRICING_TABLE: ClassVar[dict[str, dict[str, float]]] = {
        "deepseek_v3": {
            "input_per_1k": 0.00014,
            "output_per_1k": 0.00028,
            "cached_input_per_1k": 0.000014,
        },
        "deepseek_r1": {
            "input_per_1k": 0.00055,
            "output_per_1k": 0.00219,
            "cached_input_per_1k": 0.00014,
        },
        "vertex_ai": {
            "input_per_1k": 0.000125,
            "output_per_1k": 0.000375,
            "cached_input_per_1k": 0.000030,
        },
        "ollama_local": {
            "input_per_1k": 0.0,
            "output_per_1k": 0.0,
            "cached_input_per_1k": 0.0,
        },
    }

    def __init__(
        self,
        dataset_path: str = "data/benchmarks/sbv_testset_tvpl.json",
        pricing_provider: str = "deepseek_v3",
    ) -> None:
        self.dataset_path = Path(dataset_path)
        self.pricing_provider = pricing_provider
        self.pricing = self.PRICING_TABLE.get(pricing_provider, self.PRICING_TABLE["deepseek_v3"])
        self.dataset: list[dict[str, Any]] = self._load_dataset()

    def _load_dataset(self) -> list[dict[str, Any]]:
        """Loads and parses benchmark dataset."""
        if not self.dataset_path.exists():
            logger.warning(f"Dataset path {self.dataset_path} does not exist. Initializing empty.")
            return []
        try:
            with open(self.dataset_path, encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"Loaded {len(data)} SBV benchmark test queries from {self.dataset_path}")
            return cast("list[dict[str, Any]]", data) if isinstance(data, list) else []
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

            cost = (pred.input_tokens / 1000) * self.pricing["input_per_1k"] + (
                pred.output_tokens / 1000
            ) * self.pricing["output_per_1k"]
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

    @classmethod
    def estimate_suite_cost(
        cls,
        pricing_provider: str = "deepseek_v3",
        cache_hit_ratio: float = 0.5,
    ) -> dict[str, Any]:
        """Calculates token and budget estimation for the 1,180-run evaluation suite.

        Tracks (Section 9.2 in D1 Proposal):
        1. SBV 100-QA Benchmark: 100 Qs * 3 seeds = 300 runs (2.82M in, 0.51M out)
        2. Scenario Audit Tasks: 10 tasks * 3 seeds = 30 runs (0.35M in, 0.065M out)
        3. ALQAC 2025 Retrieval: 150 Qs * 3 seeds = 450 runs (2.25M in, 0.315M out)
        4. Ablation Suite: 100 Qs * 3 seeds = 300 runs (2.10M in, 0.42M out)
        5. Ragas LLM-as-a-Judge: 100 Qs = 100 runs (0.85M in, 0.12M out)
        Total: 1,180 runs | ~8.37M input tokens | ~1.43M output tokens
        """
        pricing = cls.PRICING_TABLE.get(pricing_provider, cls.PRICING_TABLE["deepseek_v3"])

        tracks = [
            ("SBV 100-QA Benchmark", 2_820_000, 510_000, 300),
            ("Scenario Audit Tasks", 350_000, 65_000, 30),
            ("ALQAC 2025 Retrieval Subset", 2_250_000, 315_000, 450),
            ("Ablation Suite", 2_100_000, 420_000, 300),
            ("Ragas LLM-as-a-Judge", 850_000, 120_000, 100),
        ]

        total_input = sum(t[1] for t in tracks)
        total_output = sum(t[2] for t in tracks)
        total_runs = sum(t[3] for t in tracks)

        in_p = pricing["input_per_1k"]
        out_p = pricing["output_per_1k"]
        cached_in_p = pricing.get("cached_input_per_1k", in_p)

        effective_in_rate = (1.0 - cache_hit_ratio) * in_p + cache_hit_ratio * cached_in_p

        cost_without_cache = (total_input / 1000) * in_p + (total_output / 1000) * out_p
        cost_with_cache = (total_input / 1000) * effective_in_rate + (total_output / 1000) * out_p

        breakdown = []
        for name, tin, tout, runs in tracks:
            c = (tin / 1000) * effective_in_rate + (tout / 1000) * out_p
            breakdown.append(
                {
                    "track": name,
                    "runs": runs,
                    "input_tokens": tin,
                    "output_tokens": tout,
                    "cost_usd": round(c, 4),
                }
            )

        return {
            "provider": pricing_provider,
            "total_runs": total_runs,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "cost_without_cache_usd": round(cost_without_cache, 4),
            "cost_with_cache_usd": round(cost_with_cache, 4),
            "cache_hit_ratio": cache_hit_ratio,
            "breakdown": breakdown,
        }
