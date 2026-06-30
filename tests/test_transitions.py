import unittest

from tools.audit import validate_audit_event
from tools.transitions import build_transition_audit_event, evaluate_stage_transition


def workflow_run(*, current_stage, steps=None, artifact_manifest=None):
    return {
        "workflow_run_id": "workflow.fixture_validation.20260630_120000",
        "workspace_id": "workspace_demo",
        "scenario_ids": ["failed_checksum"],
        "current_stage": current_stage,
        "started_at": "2026-06-30T12:00:00Z",
        "completed_at": "2026-06-30T12:01:00Z",
        "steps": steps or [],
        "artifact_manifest": artifact_manifest or {"passed": False},
    }


class TransitionsTest(unittest.TestCase):
    def test_first_transition_is_allowed_without_prior_step(self):
        result = evaluate_stage_transition(
            workflow_run(current_stage="not_started"),
            "evaluation",
        )

        self.assertTrue(result.allowed)

    def test_transition_requires_prior_step_completed(self):
        result = evaluate_stage_transition(
            workflow_run(
                current_stage="evaluation",
                steps=[
                    {
                        "step": "run_deterministic_evals",
                        "status": "failed",
                    }
                ],
            ),
            "runbook",
        )

        self.assertFalse(result.allowed)
        self.assertEqual(
            result.unmet_prerequisites,
            ("step_not_completed:run_deterministic_evals",),
        )

    def test_artifacts_written_requires_passed_manifest(self):
        result = evaluate_stage_transition(
            workflow_run(
                current_stage="artifact_validation",
                steps=[
                    {
                        "step": "validate_artifact_bundle",
                        "status": "completed",
                    }
                ],
                artifact_manifest={"passed": False},
            ),
            "artifacts_written",
        )

        self.assertFalse(result.allowed)
        self.assertIn("artifact_manifest_not_passed", result.unmet_prerequisites)

    def test_bad_stage_jump_is_blocked(self):
        result = evaluate_stage_transition(
            workflow_run(current_stage="evaluation"),
            "artifacts_written",
        )

        self.assertFalse(result.allowed)
        self.assertIn("transition_not_allowed", result.unmet_prerequisites)

    def test_transition_audit_event_is_valid(self):
        run = workflow_run(current_stage="not_started")
        result = evaluate_stage_transition(run, "evaluation")

        event = build_transition_audit_event(result, run)

        self.assertEqual(event["decision"], "transition_allowed")
        self.assertEqual(validate_audit_event(event), ())

    def test_blocked_transition_audit_event_is_valid(self):
        run = workflow_run(current_stage="evaluation")
        result = evaluate_stage_transition(run, "artifacts_written")

        event = build_transition_audit_event(result, run)

        self.assertEqual(event["decision"], "transition_blocked")
        self.assertEqual(event["status"], "blocked")
        self.assertEqual(validate_audit_event(event), ())


if __name__ == "__main__":
    unittest.main()
