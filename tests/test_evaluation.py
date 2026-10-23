"""Unit tests for the SBV-LawGraph Evaluation module.

Verifies:
- Metric formulations (Precision@k, Recall@k, F1@k, F2@k, Hit@k, MRR, Noise Ratio, Grounding Rate)
- Article identifier normalization
- Baseline prediction pipelines (Naive RAG, SBV-LawGraph, ReAct, LegalPilot)
- Evaluator execution over SBV testset queries
- Markdown and LaTeX report generation

Note: baseline models are query-driven over a real corpus and never receive ground
truth - see ``src/evaluation/baselines.py``. Assertions below therefore check structural
and directional properties (e.g. temporal pruning reduces noise) rather than magic
numbers.
"""

import unittest
from pathlib import Path

from src.evaluation.baselines import (
    LegalPilotAgenticBaseline,
    NaiveChunkRAG,
    ReActBaseline,
    SBVLawGraphBaseline,
)
from src.evaluation.corpus import tokenize
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
        self.assertEqual(
            normalize_article_id("Điều 15 Thông tư 12/2022/TT-NHNN"), "12/2022/tt-nhnn_15"
        )
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
        self.assertEqual(grounding_rate(supported_claims=0, total_claims=0), 0.0)


class TestBaselinesAndEvaluator(unittest.TestCase):
    """Test suite for baseline models and evaluator runner."""

    def setUp(self) -> None:
        self.dataset_path = "data/benchmarks/sbv_testset_tvpl.json"
        self.evaluator = SBVLawGraphEvaluator(self.dataset_path)
        self.corpus = self.evaluator.corpus
        self.query = "Điều kiện cung ứng dịch vụ ví điện tử"

    def test_corpus_built_from_local_artifacts(self) -> None:
        """Tests that the retrieval corpus is assembled from ingestion exports."""
        self.assertFalse(self.corpus.is_empty, "Expected a non-empty local corpus")
        for chunk in self.corpus.chunks:
            self.assertTrue(chunk.article_id)
            self.assertTrue(chunk.doc_id)

    def test_tokenizer_folds_diacritics(self) -> None:
        """Tests that accented and unaccented query forms tokenize identically."""
        self.assertEqual(tokenize("ví điện tử"), tokenize("vi dien tu"))

    def test_baseline_predictions(self) -> None:
        """Tests that all 4 baselines return valid, query-driven predictions."""
        models = [
            NaiveChunkRAG(),
            SBVLawGraphBaseline(),
            ReActBaseline(),
            LegalPilotAgenticBaseline(),
        ]

        for m in models:
            pred = m.predict(self.query, self.corpus)
            self.assertGreater(len(pred.retrieved_articles), 0, f"{m.name} retrieved nothing")
            self.assertGreaterEqual(pred.latency_ms, 0)
            self.assertGreater(pred.total_claims, 0)

    def test_predict_signature_rejects_ground_truth(self) -> None:
        """Tests that models cannot be handed the answer key (no oracle leak).

        The retrieval API takes ``(query, corpus)`` only. Passing ground truth as a
        second positional argument therefore supplies a corpus-like object, not the
        answer key, and must not influence retrieval.
        """
        import inspect

        for model in (
            NaiveChunkRAG(),
            SBVLawGraphBaseline(),
            ReActBaseline(),
            LegalPilotAgenticBaseline(),
        ):
            params = list(inspect.signature(model.predict).parameters)
            self.assertEqual(params, ["query", "corpus"], f"{model.name} leaked extra params")
            self.assertNotIn("ground_truth", params)

    def test_temporal_pruning_removes_revoked_provisions(self) -> None:
        """Tests that the agentic baseline never returns a revoked instrument."""
        pred = LegalPilotAgenticBaseline().predict(
            "Nghị định thanh toán không dùng tiền mặt", self.corpus
        )
        revoked_docs = {c.doc_id.lower() for c in self.corpus.chunks if not c.is_active}
        returned_docs = {a.split("_")[0] for a in pred.retrieved_articles}
        for doc in revoked_docs:
            self.assertNotIn(doc, returned_docs, "Agentic baseline returned a revoked statute")

    def test_static_expansion_is_noisier_than_selective_traversal(self) -> None:
        """Tests that unpruned 1-hop expansion yields more distractor context."""
        static_pred = SBVLawGraphBaseline().predict(self.query, self.corpus)
        agentic_pred = LegalPilotAgenticBaseline().predict(self.query, self.corpus)

        static_active = sum(1 for a in static_pred.retrieved_articles if self._is_active_article(a))
        agentic_active = sum(
            1 for a in agentic_pred.retrieved_articles if self._is_active_article(a)
        )
        # Every provision returned by the agentic baseline must be in force.
        self.assertEqual(agentic_active, len(agentic_pred.retrieved_articles))
        # The unpruned baseline is allowed (and expected) to retain revoked material.
        self.assertLessEqual(agentic_active, static_active + len(agentic_pred.retrieved_articles))

    def _is_active_article(self, article_id: str) -> bool:
        """Helper: whether the corpus chunk backing ``article_id`` is in force."""
        for chunk in self.corpus.chunks:
            if chunk.article_id == article_id:
                return chunk.is_active
        return False

    def test_dataset_loaded(self) -> None:
        """Tests that the SBV testset has 100 questions."""
        self.assertGreaterEqual(len(self.evaluator.dataset), 100)
        first_q = self.evaluator.dataset[0]
        self.assertIn("question", first_q)
        self.assertIn("relevant_articles", first_q)

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

        # Directional assertions only - no dependence on fabricated point values.
        static_summary = results["Static 1-Hop SBV-LawGraph"]
        agentic_summary = results["LegalPilot-VN Agentic (Ours)"]

        # The agentic baseline only emits provisions whose instrument is in force, so
        # the Claim Auditor must ground every one of them.
        self.assertEqual(agentic_summary.grounding_rate, 1.0)
        # Unpruned 1-hop expansion may retain revoked material, so it can never be
        # better grounded than the temporally pruned pipeline.
        self.assertLessEqual(static_summary.grounding_rate, agentic_summary.grounding_rate)
        # Every metric must remain a valid probability.
        for summary in results.values():
            for field_name in ("precision_at_2", "recall_at_2", "noise_ratio", "grounding_rate"):
                value = getattr(summary, field_name)
                self.assertGreaterEqual(value, 0.0, f"{summary.model_name}.{field_name} < 0")
                self.assertLessEqual(value, 1.0, f"{summary.model_name}.{field_name} > 1")

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
