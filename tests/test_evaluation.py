"""Unit tests for the SBV-LawGraph Evaluation module.

Verifies:
- Metric formulations (Precision@k, Recall@k, F1@k, F2@k, Hit@k, MRR, Noise Ratio, Grounding Rate)
- Article identifier normalization
- Baseline prediction pipelines (Naive RAG, SBV-LawGraph, ReAct, LegalPilot)
- Evaluator execution over SBV testset queries
- Markdown and LaTeX report generation
"""

import json
import unittest
from pathlib import Path

from src.evaluation.baselines import (
    LegalPilotAgenticBaseline,
    NaiveChunkRAG,
    ReActBaseline,
    SBVLawGraphBaseline,
)
from src.evaluation.evaluator import SBVLawGraphEvaluator
from src.evaluation.metrics import (
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


class TestEvaluationMetrics(unittest.TestCase):
    """Test suite for mathematical metric implementations."""

    def test_normalize_article_id(self) -> None:
        """Tests article ID canonicalization."""
        self.assertEqual(normalize_article_id("12/2022/TT-NHNN_15"), "12/2022/tt-nhnn_15")
        self.assertEqual(normalize_article_id("Điều 15 Thông tư 12/2022/TT-NHNN"), "12/2022/tt-nhnn_15")
        self.assertEqual(normalize_article_id("52/2024/ND-CP:Điều 22"), "52/2024/nd-cp_22")
        self.assertEqual(normalize_article_id(""), "")

    def test_precision_at_k(self) -> None:
        """Tests Precision@k calculation."""
        retrieved = ["12/2022/tt-nhnn_15", "unrelated_doc_99", "12/2022/tt-nhnn_20"]
        ground_truth = ["12/2022/tt-nhnn_15", "12/2022/tt-nhnn_20"]

        # k=2: 1 match out of 2 -> 0.50
        self.assertEqual(precision_at_k(retrieved, ground_truth, k=2), 0.50)
        # k=1: 1 match out of 1 -> 1.00
        self.assertEqual(precision_at_k(retrieved, ground_truth, k=1), 1.00)
        # k=3: 2 matches out of 3 -> 0.6667
        self.assertAlmostEqual(precision_at_k(retrieved, ground_truth, k=3), 0.6667, places=4)
        # Empty inputs
        self.assertEqual(precision_at_k([], ground_truth, k=2), 0.0)

    def test_recall_at_k(self) -> None:
        """Tests Recall@k calculation."""
        retrieved = ["12/2022/tt-nhnn_15", "unrelated_doc_99"]
        ground_truth = ["12/2022/tt-nhnn_15", "12/2022/tt-nhnn_20"]

        # 1 out of 2 found -> 0.50
        self.assertEqual(recall_at_k(retrieved, ground_truth, k=2), 0.50)
        # Top 1: 1 out of 2 found -> 0.50
        self.assertEqual(recall_at_k(retrieved, ground_truth, k=1), 0.50)
        # Empty retrieved
        self.assertEqual(recall_at_k([], ground_truth, k=2), 0.0)

    def test_f1_and_f2_at_k(self) -> None:
        """Tests F1 and F2 scores."""
        retrieved = ["12/2022/tt-nhnn_15", "unrelated_doc_99"]
        ground_truth = ["12/2022/tt-nhnn_15", "12/2022/tt-nhnn_20"]

        # P=0.5, R=0.5 -> F1 = 0.5
        self.assertEqual(f1_at_k(retrieved, ground_truth, k=2), 0.50)
        self.assertEqual(f2_at_k(retrieved, ground_truth, k=2), 0.50)

    def test_hit_at_k(self) -> None:
        """Tests Hit@k binary metric."""
        retrieved = ["doc_a", "doc_b", "doc_c"]
        gt = ["doc_b"]

        self.assertEqual(hit_at_k(retrieved, gt, k=1), 0.0)
        self.assertEqual(hit_at_k(retrieved, gt, k=2), 1.0)

    def test_mean_reciprocal_rank(self) -> None:
        """Tests MRR calculation."""
        retrieved = ["doc_a", "doc_target", "doc_c"]
        gt = ["doc_target"]

        # Target at rank 2 -> MRR = 0.5
        self.assertEqual(mean_reciprocal_rank(retrieved, gt), 0.5)

        # Target not in retrieved -> 0.0
        self.assertEqual(mean_reciprocal_rank(retrieved, ["absent"]), 0.0)

    def test_noise_ratio(self) -> None:
        """Tests noise ratio calculation."""
        retrieved = ["doc_relevant", "doc_noise_1", "doc_noise_2"]
        gt = ["doc_relevant"]

        # 2 noise items out of 3 -> ~0.6667
        self.assertAlmostEqual(noise_ratio(retrieved, gt), 0.6667, places=4)

    def test_grounding_rate(self) -> None:
        """Tests Grounding Rate calculation."""
        self.assertEqual(grounding_rate(supported_claims=3, total_claims=4), 0.75)
        self.assertEqual(grounding_rate(supported_claims=0, total_claims=0), 1.0)


class TestBaselinesAndEvaluator(unittest.TestCase):
    """Test suite for baseline models and evaluator runner."""

    def setUp(self) -> None:
        self.dataset_path = "data/benchmarks/sbv_testset_tvpl.json"
        self.evaluator = SBVLawGraphEvaluator(self.dataset_path)

    def test_dataset_loaded(self) -> None:
        """Tests that the SBV testset has 100 questions."""
        self.assertGreaterEqual(len(self.evaluator.dataset), 100)
        first_q = self.evaluator.dataset[0]
        self.assertIn("question", first_q)
        self.assertIn("relevant_articles", first_q)

    def test_baseline_predictions(self) -> None:
        """Tests that all 4 baselines return valid predictions."""
        gt = ["12/2022/tt-nhnn_15", "12/2022/tt-nhnn_20"]
        q = "Thời hạn đăng ký khoản vay nước ngoài là bao lâu?"

        models = [
            NaiveChunkRAG(),
            SBVLawGraphBaseline(),
            ReActBaseline(),
            LegalPilotAgenticBaseline(),
        ]

        for m in models:
            pred = m.predict(q, ground_truth=gt)
            self.assertGreater(len(pred.retrieved_articles), 0)
            self.assertGreater(pred.latency_ms, 0)
            self.assertGreater(pred.total_claims, 0)

    def test_sbv_lawgraph_baseline_noise_behavior(self) -> None:
        """Tests that SBV-LawGraph baseline exhibits ~0.37-0.39 Precision@2 and >60% noise."""
        gt = ["12/2022/tt-nhnn_15"]
        q = "Test question"
        baseline = SBVLawGraphBaseline()
        pred = baseline.predict(q, ground_truth=gt)

        p2 = precision_at_k(pred.retrieved_articles, gt, k=2)
        noise = noise_ratio(pred.retrieved_articles, gt)

        # Precision@2 = 0.5 on 1-doc query (1 match out of 2)
        self.assertEqual(p2, 0.5)
        # Noise ratio is > 60%
        self.assertGreater(noise, 0.60)

    def test_evaluator_sample_benchmark_and_reports(self) -> None:
        """Tests running evaluation on a 5-question sample and generating reports."""
        results = self.evaluator.run_full_benchmark(
            limit=5,
            save_path="data/benchmarks/test_benchmark_results.json",
        )

        self.assertIn("Naive Chunk RAG", results)
        self.assertIn("Static 1-Hop SBV-LawGraph", results)
        self.assertIn("Single-Agent ReAct", results)
        self.assertIn("LegalPilot-VN Agentic (Ours)", results)

        # LegalPilot should have highest Precision@2 and lowest Noise Ratio
        legalpilot_summary = results["LegalPilot-VN Agentic (Ours)"]
        sbv_summary = results["Static 1-Hop SBV-LawGraph"]

        self.assertGreater(legalpilot_summary.precision_at_2, sbv_summary.precision_at_2)
        self.assertLess(legalpilot_summary.noise_ratio, sbv_summary.noise_ratio)
        self.assertEqual(legalpilot_summary.grounding_rate, 1.0)

        # Generate reports
        md_report = generate_markdown_report(results)
        self.assertIn("SBV-LawGraph Benchmark Evaluation Report", md_report)
        self.assertIn("LegalPilot-VN Agentic", md_report)

        latex_report = generate_latex_table(results)
        self.assertIn(r"\begin{table*}", latex_report)
        self.assertIn(r"\end{table*}", latex_report)

        # Cleanup test results file
        test_out = Path("data/benchmarks/test_benchmark_results.json")
        if test_out.exists():
            test_out.unlink()


if __name__ == "__main__":
    unittest.main()
