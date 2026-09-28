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
        sample_clauses = [
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
        self.assertEqual(state.audit_report.grounding_rate, 1.0)
        self.assertTrue(state.audit_report.is_fully_verified)
        self.assertIn("Nghị định 52/2024/NĐ-CP", state.final_compliance_dossier)


if __name__ == "__main__":
    unittest.main()
