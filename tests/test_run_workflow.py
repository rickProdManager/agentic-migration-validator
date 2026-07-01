import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.run_workflow import run_fixture_workflow
from tools.run_store import read_audit_log, read_workflow_run


class RunWorkflowTest(unittest.TestCase):
    def test_early_workflow_exception_persists_failed_auditable_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with (
                patch("scripts.run_workflow.PROJECT_ROOT", root),
                patch(
                    "scripts.run_workflow.write_artifact_bundle",
                    side_effect=ConnectionError(
                        "database unavailable with raw socket detail"
                    ),
                ),
            ):
                workflow_run = run_fixture_workflow(
                    ["failed_checksum"],
                    persist=True,
                )

            persisted = read_workflow_run(root, workflow_run["workflow_run_id"])
            audit_log = read_audit_log(root, workflow_run["workflow_run_id"])

        serialized = json.dumps(workflow_run)
        self.assertEqual(workflow_run["status"], "failed")
        self.assertTrue(workflow_run["workflow_validation"]["passed"])
        self.assertTrue(workflow_run["audit_validation"]["passed"])
        self.assertTrue(workflow_run["run_state"]["passed"])
        self.assertEqual(workflow_run["failure"]["error_type"], "ConnectionError")
        self.assertEqual(
            workflow_run["failure"]["error_code"],
            "workflow_step_failed:run_deterministic_evals",
        )
        self.assertNotIn("raw socket detail", serialized)
        self.assertIsNotNone(persisted)
        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log["event_count"], workflow_run["audit_event_count"])


if __name__ == "__main__":
    unittest.main()
