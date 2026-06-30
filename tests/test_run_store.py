import tempfile
import unittest
from pathlib import Path

from tools.audit import build_audit_event
from tools.run_store import (
    latest_run_manifest,
    read_audit_log,
    read_workflow_run,
    write_run_state,
)
from tools.workflow import build_fixture_workflow_run


PASSED_MANIFEST = {
    "artifact_dir": "artifacts",
    "artifact_count": 1,
    "passed": True,
    "artifacts": [
        {
            "artifact_id": "artifact.eval_report.fixture_suite.v1",
            "path": "artifacts/eval_report.json",
            "content_hash": "sha256:abc",
        }
    ],
}


def sample_workflow_run():
    return build_fixture_workflow_run(
        scenario_ids=["failed_checksum"],
        artifact_manifest=PASSED_MANIFEST,
        started_at="2026-06-30T12:00:00Z",
        completed_at="2026-06-30T12:01:00Z",
    )


def sample_audit_events():
    return [
        build_audit_event(
            audit_event_id="audit.workflow.fixture_validation.20260630_120000.v1",
            workflow_run_id="workflow.fixture_validation.20260630_120000",
            workspace_id="workspace_demo",
            scenario_id="failed_checksum",
            actor_name="eval_runner",
            actor_type="tool",
            stage="evaluation",
            decision="stage_completed",
            status="completed",
            artifact_ids=["artifact.eval_report.fixture_suite.v1"],
            created_at="2026-06-30T12:01:00Z",
        )
    ]


class RunStoreTest(unittest.TestCase):
    def test_write_run_state_persists_run_audit_log_and_latest_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output_root = root / "runs"
            run = sample_workflow_run()

            manifest = write_run_state(
                root,
                run,
                sample_audit_events(),
                output_root=output_root,
            )

            self.assertTrue(manifest["passed"])
            self.assertEqual(manifest["workflow_run_id"], run["workflow_run_id"])
            self.assertEqual(manifest["audit_event_count"], 1)
            self.assertEqual(
                latest_run_manifest(root, output_root=output_root)["workflow_run_id"],
                run["workflow_run_id"],
            )
            self.assertEqual(
                read_workflow_run(root, run["workflow_run_id"], output_root=output_root),
                run,
            )
            self.assertEqual(
                read_audit_log(root, run["workflow_run_id"], output_root=output_root)[
                    "event_count"
                ],
                1,
            )

    def test_write_run_state_rejects_invalid_audit_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest = write_run_state(
                root,
                sample_workflow_run(),
                [{"audit_event_id": "audit.invalid.v1"}],
                output_root=root / "runs",
            )

            self.assertFalse(manifest["passed"])
            self.assertIn("missing_field", {issue["issue"] for issue in manifest["issues"]})

    def test_readers_reject_unsafe_workflow_run_ids(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            self.assertIsNone(read_workflow_run(root, "../outside", output_root=root / "runs"))
            self.assertIsNone(read_audit_log(root, "../outside", output_root=root / "runs"))


if __name__ == "__main__":
    unittest.main()
