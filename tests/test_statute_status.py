"""Tests for the canonical statutory status vocabulary.

Regression guard for the ``"active"`` vs ``"in_force"`` mismatch: the ingestion
pipeline/Neo4j/Qdrant convention is ``"in_force"``, while the hand-authored statute
catalog used ``"active"``. Validity checks that compared against a single literal
falsely reported in-force instruments as revoked, which both suppressed valid
provisions and corrupted the Claim Auditor's grounding rate.
"""

import unittest

from src.agents.claim_auditor import ClaimAuditorAgent
from src.agents.lawgraph import LawGraphAgent
from src.agents.orchestrator import LegalOrchestrator
from src.core.statute_status import (
    ACTIVE_STATUSES,
    is_active_status,
    normalize_status,
)
from src.tools.validity_checker import check_statute_validity


class TestStatuteStatusVocabulary(unittest.TestCase):
    """Unit tests for the status helper."""

    def test_both_active_literals_are_accepted(self) -> None:
        """Tests that 'active' and 'in_force' are treated as equivalent."""
        self.assertEqual(ACTIVE_STATUSES, frozenset({"active", "in_force"}))
        self.assertTrue(is_active_status("active"))
        self.assertTrue(is_active_status("in_force"))

    def test_status_matching_is_case_and_whitespace_insensitive(self) -> None:
        """Tests that stored literals are normalized before comparison."""
        self.assertTrue(is_active_status("IN_FORCE"))
        self.assertTrue(is_active_status("  in_force  "))
        self.assertTrue(is_active_status("Active"))

    def test_revoked_by_forces_inactive(self) -> None:
        """Tests that a recorded repealing instrument overrides an active literal."""
        self.assertFalse(is_active_status("in_force", "52/2024/ND-CP"))
        self.assertFalse(is_active_status("active", "168/2024/ND-CP"))

    def test_unknown_and_missing_statuses_are_inactive(self) -> None:
        """Tests that unrecognized statuses fail closed rather than open."""
        for value in (None, "", "bogus", "unknown"):
            self.assertFalse(is_active_status(value), f"{value!r} should not be active")

    def test_normalize_status_maps_to_canonical_literals(self) -> None:
        """Tests canonicalization of all known literals."""
        self.assertEqual(normalize_status("in_force"), "active")
        self.assertEqual(normalize_status("active"), "active")
        self.assertEqual(normalize_status("expired"), "expired")
        self.assertEqual(normalize_status("partially_expired"), "partially_expired")
        self.assertEqual(normalize_status(None), "unknown")


class TestInForceCircularIsNotFlagged(unittest.TestCase):
    """Regression tests for the false-positive revocation bug."""

    def setUp(self) -> None:
        self.auditor = ClaimAuditorAgent()

    def test_in_force_circular_is_grounded(self) -> None:
        """Tests that a document stored as 'in_force' is accepted as valid.

        Circular 40/2024/TT-NHNN is in force but was previously flagged as revoked
        purely because its status literal was 'in_force' rather than 'active'.
        """
        clauses = [
            {
                "doc_id": "40/2024/TT-NHNN",
                "status": "in_force",
                "revoked_by": None,
                "article": "40/2024/tt-nhnn_18",
                "article_title": "Hồ sơ mở ví điện tử",
                "content": "Hồ sơ mở ví điện tử gồm các giấy tờ sau theo quy định hiện hành.",
            }
        ]
        report = self.auditor.audit_provisions(clauses)
        self.assertEqual(report.total_claims, 1)
        self.assertEqual(report.grounded_claims, 1)
        self.assertTrue(report.is_fully_verified)
        self.assertEqual(report.unsupported_claims, [])

    def test_revoked_decree_is_still_flagged(self) -> None:
        """Tests that the fix did not weaken genuine revocation detection."""
        clauses = [
            {
                "doc_id": "101/2012/ND-CP",
                "status": "expired",
                "revoked_by": "52/2024/ND-CP",
                "article": "101/2012/nd-cp_15",
                "article_title": "Điều kiện cấp phép (cũ)",
                "content": "Quy định cũ đã hết hiệu lực theo Nghị định 52/2024/NĐ-CP.",
            }
        ]
        report = self.auditor.audit_provisions(clauses)
        self.assertFalse(report.is_fully_verified)
        self.assertEqual(len(report.unsupported_claims), 1)

    def test_validity_checker_reports_in_force_document_as_valid(self) -> None:
        """Tests that the ADK validity tool agrees with the auditor."""
        result = check_statute_validity("52/2024/ND-CP")
        self.assertTrue(result["is_valid"], "Decree 52/2024 should be valid")

    def test_validity_checker_rejects_unknown_document(self) -> None:
        """Tests that unknown documents are reported as invalid."""
        result = check_statute_validity("99/9999/XX-YY")
        self.assertFalse(result["is_valid"])
        self.assertEqual(result["status"], "unknown")


class TestOrchestratorKeepsInForceProvisions(unittest.TestCase):
    """End-to-end check that the pipeline no longer prunes in-force guidance."""

    def test_pipeline_retains_in_force_circular(self) -> None:
        """Tests that Circular 40/2024 survives the recovery loop.

        Before the fix the orchestrator pruned it as revoked, discarding the
        implementing guidance that supplies the filing forms.
        """
        orchestrator = LegalOrchestrator()
        subgoals, keywords = orchestrator.plan_subgoals(
            "doanh nghiệp fintech xin cấp phép ví điện tử"
        )
        provisions = LawGraphAgent().retrieve_provisions(subgoals=subgoals, keywords=keywords)
        report = orchestrator.auditor_agent.audit_provisions(provisions)

        cited = {p.get("doc_id") for p in provisions}
        self.assertIn("40/2024/TT-NHNN", cited)

        flagged = {u.cited_statute for u in report.unsupported_claims}
        self.assertNotIn(
            "40/2024/TT-NHNN",
            flagged,
            "In-force circular must not be flagged as revoked",
        )
        # The genuinely revoked decree must still be caught.
        self.assertIn("101/2012/ND-CP", flagged)


if __name__ == "__main__":
    unittest.main()
