import unittest

from tools.gatekeeper import GateContext, evaluate_cutover_readiness, evaluate_gate


def finding(
    finding_key="validation.checksum_mismatch:public.payments:*",
    *,
    risk_axis="migration_integrity",
    severity="high",
    gate_effect=("blocks_cutover", "blocks_ready"),
    status="unresolved",
):
    return {
        "record_type": "detector_finding",
        "risk_axis": risk_axis,
        "finding_key": finding_key,
        "finding_type": finding_key.split(":")[0],
        "detector": "test",
        "severity": severity,
        "status": status,
        "gate_effect": list(gate_effect),
    }


READY_CONTEXT = GateContext(
    validation_completed=True,
    validation_accepted=True,
    final_runbook_published=True,
    approvals=("validation_acceptance", "cutover_recommendation", "ready"),
)


class GatekeeperTest(unittest.TestCase):
    def test_cutover_and_ready_allowed_when_only_advisory_findings_exist(self):
        result = evaluate_cutover_readiness(
            [
                finding(
                    finding_key="schema.type_widened:public.orders:total_amount",
                    risk_axis="compatibility_advisory",
                    severity="low",
                    gate_effect=(),
                )
            ],
            READY_CONTEXT,
        )

        self.assertTrue(result["can_recommend_cutover"]["allowed"])
        self.assertTrue(result["can_mark_ready"]["allowed"])

    def test_blocking_integrity_finding_blocks_cutover_and_ready(self):
        result = evaluate_cutover_readiness([finding()], READY_CONTEXT)

        self.assertFalse(result["can_recommend_cutover"]["allowed"])
        self.assertFalse(result["can_mark_ready"]["allowed"])
        self.assertEqual(
            result["can_recommend_cutover"]["blocking_findings"],
            ["validation.checksum_mismatch:public.payments:*"],
        )

    def test_compatibility_advisory_cannot_block_cutover_even_with_gate_effect(self):
        result = evaluate_cutover_readiness(
            [
                finding(
                    finding_key="compatibility.unsupported_feature:public.orders:trigger",
                    risk_axis="compatibility_advisory",
                    severity="high",
                )
            ],
            READY_CONTEXT,
        )

        self.assertTrue(result["can_recommend_cutover"]["allowed"])
        self.assertTrue(result["can_mark_ready"]["allowed"])

    def test_resolved_and_accepted_risk_findings_do_not_block(self):
        result = evaluate_cutover_readiness(
            [
                finding(status="resolved"),
                finding(
                    finding_key="validation.duplicate_values_after_unique_relaxation:public.payments:key",
                    status="accepted_risk",
                ),
            ],
            READY_CONTEXT,
        )

        self.assertTrue(result["can_recommend_cutover"]["allowed"])
        self.assertTrue(result["can_mark_ready"]["allowed"])

    def test_unresolved_critical_integrity_finding_blocks_without_gate_effect(self):
        result = evaluate_cutover_readiness(
            [
                finding(
                    finding_key="risk.derived.compounding_high_validation_failures:public:*",
                    severity="critical",
                    gate_effect=(),
                )
            ],
            READY_CONTEXT,
        )

        self.assertFalse(result["can_recommend_cutover"]["allowed"])
        self.assertFalse(result["can_mark_ready"]["allowed"])
        self.assertEqual(
            result["can_mark_ready"]["blocking_findings"],
            ["risk.derived.compounding_high_validation_failures:public:*"],
        )

    def test_missing_approval_blocks_gate(self):
        result = evaluate_gate(
            "can_recommend_cutover",
            [],
            GateContext(validation_accepted=True),
        )

        self.assertFalse(result.allowed)
        self.assertEqual(result.missing_approvals, ("cutover_recommendation",))

    def test_unmet_prerequisite_blocks_gate(self):
        result = evaluate_gate(
            "can_mark_ready",
            [],
            GateContext(approvals=("ready",), final_runbook_published=True),
        )

        self.assertFalse(result.allowed)
        self.assertEqual(result.unmet_prerequisites, ("validation_accepted",))

    def test_unresolved_evidence_blocks_gate(self):
        result = evaluate_gate(
            "can_accept_validation",
            [],
            GateContext(
                validation_completed=True,
                approvals=("validation_acceptance",),
                required_evidence_refs=("validation.checksum.public.payments.v1",),
                resolved_evidence_refs=(),
            ),
        )

        self.assertFalse(result.allowed)
        self.assertEqual(
            result.unresolved_evidence_refs,
            ("validation.checksum.public.payments.v1",),
        )


if __name__ == "__main__":
    unittest.main()
