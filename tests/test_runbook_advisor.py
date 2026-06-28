import unittest

from tools.runbook_advisor import generate_runbook_draft, validate_runbook_boundary


CHECKSUM_FINDING = {
    "record_type": "detector_finding",
    "risk_axis": "migration_integrity",
    "finding_key": "validation.checksum_mismatch:public.customers:*",
    "finding_type": "validation.checksum_mismatch",
    "detector": "canonical_checksum",
    "severity": "high",
    "status": "unresolved",
    "gate_effect": ["blocks_cutover", "blocks_ready"],
    "evidence_refs": ["validation.checksum.public.customers.v1"],
    "summary": "Canonical checksum mismatch for public.customers.",
}


BLOCKED_GATES = {
    "can_recommend_cutover": {
        "gate": "can_recommend_cutover",
        "allowed": False,
        "blocking_findings": ["validation.checksum_mismatch:public.customers:*"],
    },
    "can_mark_ready": {
        "gate": "can_mark_ready",
        "allowed": False,
        "blocking_findings": ["validation.checksum_mismatch:public.customers:*"],
    },
}


ALLOWED_GATES = {
    "can_recommend_cutover": {
        "gate": "can_recommend_cutover",
        "allowed": True,
        "blocking_findings": [],
    },
    "can_mark_ready": {
        "gate": "can_mark_ready",
        "allowed": True,
        "blocking_findings": [],
    },
}


class RunbookAdvisorTest(unittest.TestCase):
    def claims_by_key(self, runbook):
        return {claim["claim_key"]: claim for claim in runbook["claims"]}

    def test_blocked_recommendation_cites_gate_and_blocking_finding_evidence(self):
        runbook = generate_runbook_draft(
            scenario_id="failed_checksum",
            validation_findings=[CHECKSUM_FINDING],
            gate_results=BLOCKED_GATES,
        )
        claims = self.claims_by_key(runbook)
        recommendation = claims["recommendation.can_mark_ready.blocked"]

        self.assertTrue(runbook["boundary_validation"]["passed"])
        self.assertIn("gate.can_mark_ready.failed_checksum.v1", recommendation["evidence_refs"])
        self.assertIn("validation.checksum.public.customers.v1", recommendation["evidence_refs"])
        self.assertEqual(
            recommendation["finding_keys"],
            ["validation.checksum_mismatch:public.customers:*"],
        )
        self.assertIn("Do not proceed", recommendation["claim"])

    def test_allowed_recommendation_still_cites_gate_result(self):
        runbook = generate_runbook_draft(
            scenario_id="clean_migration",
            gate_results=ALLOWED_GATES,
        )
        claims = self.claims_by_key(runbook)
        recommendation = claims["recommendation.can_mark_ready.allowed"]

        self.assertTrue(runbook["boundary_validation"]["passed"])
        self.assertEqual(
            recommendation["evidence_refs"],
            ["gate.can_mark_ready.clean_migration.v1"],
        )
        self.assertEqual(recommendation["finding_keys"], [])
        self.assertIn("allowed by deterministic gates", recommendation["claim"])

    def test_finding_summary_restates_finding_summary_with_finding_evidence(self):
        runbook = generate_runbook_draft(
            scenario_id="failed_checksum",
            validation_findings=[CHECKSUM_FINDING],
            gate_results=BLOCKED_GATES,
        )
        claim = self.claims_by_key(runbook)[
            "finding.validation.checksum_mismatch:public.customers:*"
        ]

        self.assertEqual(claim["claim"], "Canonical checksum mismatch for public.customers.")
        self.assertEqual(claim["evidence_refs"], ["validation.checksum.public.customers.v1"])
        self.assertEqual(
            claim["finding_keys"],
            ["validation.checksum_mismatch:public.customers:*"],
        )

    def test_missing_gate_result_emits_insufficient_evidence_claim(self):
        runbook = generate_runbook_draft(
            scenario_id="unknown_state",
            validation_findings=[CHECKSUM_FINDING],
            gate_results={},
        )
        claims = self.claims_by_key(runbook)

        self.assertTrue(runbook["boundary_validation"]["passed"])
        self.assertEqual(runbook["summary"]["can_mark_ready"], None)
        self.assertIn(
            "insufficient evidence",
            claims["recommendation.can_mark_ready.insufficient_evidence"]["claim"],
        )

    def test_boundary_validation_rejects_recommendation_without_gate_evidence(self):
        runbook = {
            "claims": [
                {
                    "claim_key": "recommendation.bad",
                    "claim_type": "recommendation",
                    "claim": "Proceed.",
                    "evidence_refs": ["validation.checksum.public.customers.v1"],
                }
            ]
        }

        issues = validate_runbook_boundary(runbook)

        self.assertEqual(issues[0].issue, "missing_gate_evidence_ref")


if __name__ == "__main__":
    unittest.main()
