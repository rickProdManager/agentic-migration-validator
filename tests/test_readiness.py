import unittest

from tools.approvals import build_approval_record
from tools.readiness import build_readiness_view


def workflow_run(scenario_id="clean_migration"):
    return {
        "workflow_run_id": "workflow.fixture_validation.20260630_120000",
        "workspace_id": "workspace_demo",
        "status": "completed",
        "current_stage": "artifacts_written",
        "completed_at": "2026-06-30T12:01:00Z",
        "steps": [
            {"step": "run_deterministic_evals", "status": "completed"},
            {"step": "generate_runbook_drafts", "status": "completed"},
            {"step": "validate_artifact_bundle", "status": "completed"},
            {"step": "write_artifact_bundle", "status": "completed"},
        ],
        "artifact_refs": [
            "artifact.eval_report.fixture_suite.v1",
            f"artifact.runbook_draft.{scenario_id}.v1",
        ],
        "artifact_manifest": {"passed": True},
    }


def approval_log(*approval_types):
    approvals = [
        build_approval_record(
            workflow_run_id="workflow.fixture_validation.20260630_120000",
            workspace_id="workspace_demo",
            scenario_id="clean_migration",
            gate=gate,
            actor="human.reviewer",
            decision="approved",
            evidence_refs=["artifact.eval_report.fixture_suite.v1"],
            created_at=f"2026-06-30T12:0{index}:00Z",
        )
        for index, gate in enumerate(
            {
                "validation_acceptance": "can_accept_validation",
                "cutover_recommendation": "can_recommend_cutover",
                "ready": "can_mark_ready",
            }[approval_type]
            for approval_type in approval_types
        )
    ]
    return {
        "approval_count": len(approvals),
        "approvals": approvals,
    }


def eval_report(scenario_id="clean_migration", findings=None):
    return {
        "scenarios": [
            {
                "scenario_id": scenario_id,
                "validation_findings": findings or [],
                "schema_findings": [],
            }
        ]
    }


CHECKSUM_FINDING = {
    "record_type": "detector_finding",
    "risk_axis": "migration_integrity",
    "finding_key": "validation.checksum_mismatch:public.customers:*",
    "finding_type": "validation.checksum_mismatch",
    "severity": "high",
    "status": "unresolved",
    "gate_effect": ["blocks_cutover", "blocks_ready"],
}


class ReadinessTest(unittest.TestCase):
    def test_readiness_view_reports_missing_approvals(self):
        view = build_readiness_view(workflow_run(), approval_log(), eval_report())
        scenario = view["scenarios"][0]

        self.assertFalse(scenario["gate_results"]["can_accept_validation"]["allowed"])
        self.assertEqual(
            scenario["gate_results"]["can_accept_validation"]["missing_approvals"],
            ["validation_acceptance"],
        )
        self.assertIn("validation_acceptance", view["approval_state"]["pending_approvals"])

    def test_validation_approval_satisfies_accept_validation_gate(self):
        view = build_readiness_view(
            workflow_run(),
            approval_log("validation_acceptance"),
            eval_report(),
        )
        scenario = view["scenarios"][0]

        self.assertTrue(scenario["gate_results"]["can_accept_validation"]["allowed"])
        self.assertFalse(scenario["gate_results"]["can_recommend_cutover"]["allowed"])
        self.assertEqual(
            scenario["gate_results"]["can_recommend_cutover"]["missing_approvals"],
            ["cutover_recommendation"],
        )

    def test_all_required_approvals_allow_clean_ready_gates(self):
        view = build_readiness_view(
            workflow_run(),
            approval_log("validation_acceptance", "cutover_recommendation", "ready"),
            eval_report(),
        )
        scenario = view["scenarios"][0]

        self.assertTrue(scenario["cutover_ready"])
        self.assertTrue(scenario["migration_ready"])

    def test_findings_still_block_even_with_approvals(self):
        view = build_readiness_view(
            workflow_run("failed_checksum"),
            approval_log("validation_acceptance", "cutover_recommendation", "ready"),
            eval_report("failed_checksum", findings=[CHECKSUM_FINDING]),
        )
        scenario = view["scenarios"][0]

        self.assertFalse(scenario["cutover_ready"])
        self.assertFalse(scenario["migration_ready"])
        self.assertEqual(
            scenario["gate_results"]["can_recommend_cutover"]["blocking_findings"],
            ["validation.checksum_mismatch:public.customers:*"],
        )


if __name__ == "__main__":
    unittest.main()
