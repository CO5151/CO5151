"""Unit tests for the LegalPilot-VN Agents module.

Tests the multi-agent pipeline:
- LawGraphAgent provision retrieval
- ClaimAuditorAgent detection of revoked documents
- DrafterAgent compliance dossier formatting
- LegalOrchestrator end-to-end execution and re-routing loop
"""

import contextlib
import unittest
from pathlib import Path
from typing import Any

from src.agents.claim_auditor import ClaimAuditorAgent
from src.agents.drafter import DrafterAgent
from src.agents.lawgraph import LawGraphAgent
from src.agents.orchestrator import LegalOrchestrator
from src.memory.sqlite_manager import SQLiteMemoryManager
from src.memory.state_models import EnterpriseProfile


class TestLegalAgents(unittest.TestCase):
    """Test suite for simple multi-agent legal pipeline."""

    def setUp(self) -> None:
        self.test_db_path = "data/test_agents_memory.db"
        self.memory = SQLiteMemoryManager(self.test_db_path)
        self.orchestrator = LegalOrchestrator(memory_manager=self.memory, max_retries=2)
        self.lawgraph = LawGraphAgent()
        self.auditor = ClaimAuditorAgent(memory_manager=self.memory)
        self.drafter = DrafterAgent()

    def tearDown(self) -> None:
        # Clean up test database
        p = Path(self.test_db_path)
        if p.exists():
            with contextlib.suppress(OSError):
                p.unlink()

    def test_lawgraph_retrieval(self) -> None:
        """Tests that LawGraphAgent retrieves matching provisions."""
        provisions = self.lawgraph.retrieve_provisions(
            subgoals=["Xác định điều kiện cấp phép ví điện tử"],
            keywords=["ví điện tử", "thanh toán không dùng tiền mặt"],
        )
        self.assertGreater(len(provisions), 0)
        doc_ids = [p["doc_id"] for p in provisions]
        self.assertIn("52/2024/ND-CP", doc_ids)

    def test_claim_auditor_detects_revoked_document(self) -> None:
        """Tests that ClaimAuditorAgent flags expired statutes and computes grounding rate."""
        sample_clauses: list[dict[str, Any]] = [
            {
                "doc_id": "101/2012/ND-CP",
                "status": "expired",
                "revoked_by": "52/2024/ND-CP",
                "content": "Vốn 50 tỷ",
            },
            {
                "doc_id": "52/2024/ND-CP",
                "status": "active",
                "revoked_by": None,
                "content": "Vốn 50 tỷ đồng theo luật mới.",
            },
        ]
        report = self.auditor.audit_provisions(sample_clauses)
        self.assertEqual(report.total_claims, 2)
        self.assertEqual(report.grounded_claims, 1)
        self.assertFalse(report.is_fully_verified)
        self.assertEqual(len(report.unsupported_claims), 1)
        self.assertEqual(report.unsupported_claims[0].cited_statute, "101/2012/ND-CP")

    def test_drafter_synthesizes_dossier(self) -> None:
        """Tests that DrafterAgent produces formatted dossier with disclaimers."""
        active_clauses = [
            {
                "doc_id": "52/2024/ND-CP",
                "title": "Nghị định 52/2024/NĐ-CP",
                "article": "Điều 22",
                "effective_date": "2024-07-01",
                "content": "Vốn điều lệ tối thiểu 50 tỷ.",
            }
        ]
        report = self.auditor.audit_provisions(active_clauses)
        profile = EnterpriseProfile(
            company_name="Test FinTech JSC",
            entity_type="Cổ phần",
            charter_capital=60_000_000_000,
            sector_code="6419",
            headcount=30,
        )
        dossier = self.drafter.synthesize_dossier("Query test", active_clauses, report, profile)
        self.assertIn("BÁO CÁO TƯ VẤN TUÂN THỦ PHÁP LÝ", dossier)
        self.assertIn("Nghị định 52/2024/NĐ-CP", dossier)
        self.assertIn("MIỄN TRỪ TRÁCH NHIỆM", dossier)

    def test_orchestrator_pipeline_end_to_end(self) -> None:
        """Tests full pipeline run with re-routing and SQLite persistence."""
        profile = EnterpriseProfile(
            company_name="Global FDI Payment Ltd",
            entity_type="Doanh nghiệp FDI",
            charter_capital=30_000_000_000,
            sector_code="6419",
            headcount=20,
            foreign_ownership_ratio=0.49,
        )
        query = "Tư vấn điều kiện cấp phép ví điện tử cho nhà đầu tư ngoại năm 2024"
        state = self.orchestrator.run(query, enterprise_profile=profile)

        self.assertTrue(state.is_completed)
        self.assertIsNotNone(state.final_compliance_dossier)
        self.assertIsNotNone(state.audit_report)
        assert state.audit_report is not None
        assert state.final_compliance_dossier is not None
        self.assertEqual(state.audit_report.grounding_rate, 1.0)
        self.assertTrue(state.audit_report.is_fully_verified)
        self.assertIn("Nghị định 52/2024/NĐ-CP", state.final_compliance_dossier)

    def test_lawgraph_trace_selective_edge_tool(self) -> None:
        """Tests that trace_selective_edge tool returns structured traversal output."""
        from src.tools.lawgraph_tool import trace_selective_edge

        res = trace_selective_edge("52/2024/ND-CP", reference_date="2024-08-01")
        self.assertIn("seed_doc_id", res)
        self.assertEqual(res["seed_doc_id"], "52/2024/ND-CP")
        self.assertIn("noise_reduction_ratio", res)

    def test_query_lawgraph_tool(self) -> None:
        """Tests that query_lawgraph tool retrieves relevant statutory provisions."""
        from src.tools.lawgraph_tool import query_lawgraph

        provisions = query_lawgraph("ví điện tử thanh toán", top_k=3)
        self.assertGreater(len(provisions), 0)
        self.assertLessEqual(len(provisions), 3)

    def test_lawgraph_dynamic_fallback(self) -> None:
        """Tests that LawGraphAgent handles live_db fallback without crashing."""
        agent = LawGraphAgent(use_live_db=True)
        # Querying an unknown doc ID triggers dynamic graph lookup
        provisions = agent.retrieve_provisions(
            subgoals=["Tra cứu văn bản 999/2026/ND-CP"],
            keywords=["999/2026/ND-CP"],
            force_live_db=True,
        )
        self.assertIsInstance(provisions, list)

    def test_claim_auditor_live_vbpl_verification(self) -> None:
        """Tests that ClaimAuditorAgent queries live VBPL status and populates verifications."""
        sample_clauses: list[dict[str, Any]] = [
            {
                "doc_id": "52/2024/ND-CP",
                "status": "active",
                "revoked_by": None,
                "content": "Quy định về thanh toán không dùng tiền mặt vốn tối thiểu 50 tỷ.",
            }
        ]
        # Test with enable_live_vbpl=True
        report_live = self.auditor.audit_provisions(sample_clauses, enable_live_vbpl=True)
        self.assertGreater(len(report_live.live_verifications), 0)
        v = report_live.live_verifications[0]
        self.assertEqual(v["doc_id"], "52/2024/ND-CP")
        self.assertIn(v["source"], ("statute_cache", "vbpl.vn", "offline_catalog"))
        self.assertTrue(report_live.claims[0].live_verification is not None)

        # Test with enable_live_vbpl=False
        report_disabled = self.auditor.audit_provisions(sample_clauses, enable_live_vbpl=False)
        self.assertEqual(len(report_disabled.live_verifications), 0)
        self.assertIsNone(report_disabled.claims[0].live_verification)

    def test_orchestrator_live_vbpl_pipeline(self) -> None:
        """Tests that LegalOrchestrator records live_verifications in state."""
        query = "Điều kiện cấp phép ví điện tử năm 2024"
        state = self.orchestrator.run(query=query, enable_live_vbpl=True)
        self.assertTrue(state.is_completed)
        self.assertGreater(len(state.live_verifications), 0)
        doc_ids = [v["doc_id"] for v in state.live_verifications]
        self.assertTrue(any("52/2024" in d or "101/2012" in d for d in doc_ids))


if __name__ == "__main__":
    unittest.main()
