import unittest

from tools.audit import validate_audit_log
from tools.workflow import (
    build_fixture_workflow_audit_log,
    build_fixture_workflow_run,
    validate_workflow_run,
)


PASSED_MANIFEST = {
    "artifact_dir": "artifacts",
    "artifact_count": 2,
    "passed": True,
    "artifacts": [
        {
            "artifact_id": "artifact.eval_report.fixture_suite.v1",
            "path": "artifacts/eval_report.json",
            "content_hash": "sha256:abc",
        },
        {
            "artifact_id": "artifact.evidence_registry.fixture_suite.v1",
            "path": "artifacts/evidence_registry.json",
            "content_hash": "sha256:def",
        },
    ],
}


FAILED_MANIFEST = {
    "artifact_dir": "artifacts",
    "passed": False,
    "issues": [
        {
            "path": "scenarios/failed_checksum/runbook.json.boundary_validation",
            "issue": "runbook_boundary_failed",
        }
    ],
}


class WorkflowTest(unittest.TestCase):
    def test_build_fixture_workflow_run_wraps_passed_artifact_manifest(self):
        run = build_fixture_workflow_run(
            scenario_ids=["failed_checksum"],
            artifact_manifest=PASSED_MANIFEST,
            started_at="2026-06-29T12:00:00Z",
            completed_at="2026-06-29T12:01:00Z",
        )

        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["current_stage"], "artifacts_written")
        self.assertEqual(
            run["workflow_run_id"],
            "workflow.fixture_validation.20260629_120000",
        )
        self.assertEqual(
            run["artifact_refs"],
            [
                "artifact.eval_report.fixture_suite.v1",
                "artifact.evidence_registry.fixture_suite.v1",
            ],
        )
        self.assertEqual({step["status"] for step in run["steps"]}, {"completed"})
        self.assertEqual(
            [transition["to_stage"] for transition in run["stage_transitions"]],
            ["evaluation", "runbook", "artifact_validation", "artifacts_written"],
        )
        self.assertTrue(all(transition["allowed"] for transition in run["stage_transitions"]))
        self.assertEqual(validate_workflow_run(run), ())

    def test_build_fixture_workflow_audit_log_links_artifacts(self):
        run = build_fixture_workflow_run(
            scenario_ids=["failed_checksum"],
            artifact_manifest=PASSED_MANIFEST,
            started_at="2026-06-29T12:00:00Z",
            completed_at="2026-06-29T12:01:00Z",
        )

        events = build_fixture_workflow_audit_log(run)
        write_event = events[-1]

        self.assertEqual(len(events), 8)
        self.assertEqual(validate_audit_log(events), ())
        self.assertEqual(write_event["decision"], "artifact_generated")
        self.assertEqual(write_event["scenario_id"], "failed_checksum")
        self.assertEqual(
            write_event["artifact_ids"],
            [
                "artifact.eval_report.fixture_suite.v1",
                "artifact.evidence_registry.fixture_suite.v1",
            ],
        )

    def test_build_fixture_workflow_run_surfaces_artifact_validation_failure(self):
        run = build_fixture_workflow_run(
            scenario_ids=["failed_checksum"],
            artifact_manifest=FAILED_MANIFEST,
            started_at="2026-06-29T12:00:00Z",
            completed_at="2026-06-29T12:01:00Z",
        )
        steps = {step["step"]: step["status"] for step in run["steps"]}

        self.assertEqual(run["status"], "failed")
        self.assertEqual(run["current_stage"], "artifact_validation")
        self.assertEqual(steps["validate_artifact_bundle"], "failed")
        self.assertEqual(steps["write_artifact_bundle"], "skipped")
        self.assertFalse(run["stage_transitions"][-1]["allowed"])
        self.assertEqual(run["stage_transitions"][-1]["to_stage"], "artifacts_written")
        self.assertEqual(validate_workflow_run(run), ())

    def test_build_fixture_workflow_audit_log_marks_skipped_write_blocked(self):
        run = build_fixture_workflow_run(
            scenario_ids=["failed_checksum"],
            artifact_manifest=FAILED_MANIFEST,
            started_at="2026-06-29T12:00:00Z",
            completed_at="2026-06-29T12:01:00Z",
        )

        events = build_fixture_workflow_audit_log(run)

        self.assertEqual(events[-1]["status"], "blocked")
        self.assertEqual(events[-1]["decision"], "stage_completed")
        self.assertIn("transition_blocked", [event["decision"] for event in events])
        self.assertEqual(validate_audit_log(events), ())

    def test_validate_workflow_run_rejects_completed_run_without_passed_manifest(self):
        run = build_fixture_workflow_run(
            scenario_ids=["failed_checksum"],
            artifact_manifest=FAILED_MANIFEST,
            started_at="2026-06-29T12:00:00Z",
            completed_at="2026-06-29T12:01:00Z",
        )
        run["status"] = "completed"

        issues = validate_workflow_run(run)

        self.assertIn("manifest_not_passed", {issue.issue for issue in issues})

    def test_validate_workflow_run_rejects_unknown_steps(self):
        run = build_fixture_workflow_run(
            scenario_ids=["failed_checksum"],
            artifact_manifest=PASSED_MANIFEST,
            started_at="2026-06-29T12:00:00Z",
            completed_at="2026-06-29T12:01:00Z",
        )
        run["steps"].append(
            {
                "step": "unexpected",
                "status": "completed",
                "model_calls": "disabled",
            }
        )

        issues = validate_workflow_run(run)

        self.assertIn("unexpected_steps", {issue.issue for issue in issues})


if __name__ == "__main__":
    unittest.main()
