import unittest

from tools.runbook_advisor import (
    build_live_model_prompt,
    generate_runbook_draft,
    validate_runbook_boundary,
)


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

    def test_boundary_validation_rejects_referentially_valid_causal_overclaim(self):
        runbook = generate_runbook_draft(
            scenario_id="failed_checksum",
            validation_findings=[CHECKSUM_FINDING],
            gate_results=BLOCKED_GATES,
            model_narrative=(
                "The checksum mismatch indicates data corruption during transfer."
            ),
        )
        issues = runbook["boundary_validation"]["issues"]

        self.assertFalse(runbook["boundary_validation"]["passed"])
        self.assertIn(
            {
                "claim_key": "model.narrative",
                "issue": "unsupported_causal_language",
            },
            issues,
        )

    def test_boundary_validation_allows_supported_model_narrative(self):
        runbook = generate_runbook_draft(
            scenario_id="failed_checksum",
            validation_findings=[CHECKSUM_FINDING],
            gate_results=BLOCKED_GATES,
            model_narrative=(
                "can_mark_ready is blocked. Resolve or accept the listed blocking "
                "finding through the workflow before continuing."
            ),
        )

        self.assertTrue(runbook["boundary_validation"]["passed"])
        self.assertEqual(runbook["model_calls"], "enabled")
        self.assertEqual(runbook["metadata"]["model_calls"], "enabled")

    def test_boundary_validation_allows_causal_phrase_only_when_supported_by_evidence(self):
        finding_with_cause = {
            **CHECKSUM_FINDING,
            "summary": "Target data corruption is confirmed by deterministic validation.",
        }
        runbook = generate_runbook_draft(
            scenario_id="failed_checksum",
            validation_findings=[finding_with_cause],
            gate_results=BLOCKED_GATES,
            model_narrative=(
                "Target data corruption is confirmed by deterministic validation."
            ),
        )

        self.assertTrue(runbook["boundary_validation"]["passed"])

    def test_live_model_prompt_preserves_evidence_boundary(self):
        runbook = generate_runbook_draft(
            scenario_id="failed_checksum",
            validation_findings=[CHECKSUM_FINDING],
            gate_results=BLOCKED_GATES,
        )
        prompt = build_live_model_prompt(runbook)

        self.assertIn("Use only the JSON evidence below.", prompt)
        self.assertIn("Do not decide safety", prompt)
        self.assertIn("Do not claim root cause", prompt)
        self.assertIn("insufficient evidence", prompt)


if __name__ == "__main__":
    unittest.main()
