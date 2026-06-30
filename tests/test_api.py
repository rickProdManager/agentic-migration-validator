import json
import tempfile
import unittest
from pathlib import Path

from tools.api import (
    artifact_response,
    evidence_response,
    health_response,
    latest_manifest_response,
    latest_workflow_run_response,
    scenarios_response,
    validate_requested_scenarios,
    workflow_audit_response,
    workflow_run_response,
)


class ApiTest(unittest.TestCase):
    def test_health_response_reports_version(self):
        response = health_response()

        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["version"], "0.1.0")

    def test_scenarios_response_reads_fixture_manifests(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.write_scenario(
                root,
                "demo",
                description="Demo scenario.",
                critical_tables=["customers"],
            )

            response = scenarios_response(root)

        self.assertEqual(
            response,
            {
                "scenarios": [
                    {
                        "scenario_id": "demo",
                        "description": "Demo scenario.",
                        "critical_tables": ["customers"],
                        "expected_results": "fixtures/scenarios/demo/expected_findings.json",
                    }
                ]
            },
        )

    def test_validate_requested_scenarios_accepts_empty_selection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.write_scenario(root, "demo")

            response = validate_requested_scenarios(root, [])

        self.assertIsNone(response)

    def test_validate_requested_scenarios_accepts_known_selection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.write_scenario(root, "clean_migration")
            self.write_scenario(root, "failed_checksum")

            response = validate_requested_scenarios(
                root,
                ["clean_migration", "failed_checksum"],
            )

        self.assertIsNone(response)

    def test_validate_requested_scenarios_rejects_unknown_selection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.write_scenario(root, "clean_migration")

            status, response = validate_requested_scenarios(
                root,
                ["clean_migration", "missing"],
            )

        self.assertEqual(status, 400)
        self.assertEqual(response["error"]["code"], "unknown_scenario")
        self.assertIn("missing", response["error"]["message"])

    def test_latest_manifest_response_returns_404_when_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            status, response = latest_manifest_response(Path(tmpdir))

        self.assertEqual(status, 404)
        self.assertEqual(response["error"]["code"], "artifact_manifest_not_found")

    def test_latest_manifest_response_reads_manifest(self):
        manifest = {"passed": True, "artifact_count": 1}
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            (artifacts / "manifest.json").write_text(json.dumps(manifest))

            status, response = latest_manifest_response(root)

        self.assertEqual(status, 200)
        self.assertEqual(response, manifest)

    def test_artifact_response_returns_artifact_content_by_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifact = {
                "metadata": {
                    "artifact_id": "artifact.eval_report.fixture_suite.v1",
                    "content_hash": "sha256:abc",
                },
                "passed": True,
            }
            self.write_artifact_store(
                root,
                manifest_artifacts=[
                    {
                        "artifact_id": "artifact.eval_report.fixture_suite.v1",
                        "path": str(root / "artifacts" / "eval_report.json"),
                        "content_hash": "sha256:abc",
                    }
                ],
                files={"eval_report.json": artifact},
            )

            status, response = artifact_response(
                root,
                "artifact.eval_report.fixture_suite.v1",
            )

        self.assertEqual(status, 200)
        self.assertEqual(response["artifact_id"], "artifact.eval_report.fixture_suite.v1")
        self.assertEqual(response["content"], artifact)
        self.assertEqual(response["metadata"], artifact["metadata"])

    def test_artifact_response_returns_404_for_unknown_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.write_artifact_store(root, manifest_artifacts=[], files={})

            status, response = artifact_response(root, "artifact.missing.v1")

        self.assertEqual(status, 404)
        self.assertEqual(response["error"]["code"], "artifact_not_found")

    def test_artifact_response_rejects_paths_outside_artifact_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.write_artifact_store(
                root,
                manifest_artifacts=[
                    {
                        "artifact_id": "artifact.bad.v1",
                        "path": str(root / "outside.json"),
                        "content_hash": "sha256:abc",
                    }
                ],
                files={},
            )

            status, response = artifact_response(root, "artifact.bad.v1")

        self.assertEqual(status, 500)
        self.assertEqual(response["error"]["code"], "artifact_path_outside_store")

    def test_evidence_response_resolves_registry_entry(self):
        entry = {
            "evidence_ref": "validation.checksum.public.customers.v1",
            "source_artifact_id": "artifact.eval_report.fixture_suite.v1",
            "source_artifact_path": "eval_report.json",
            "content_hash": "sha256:abc",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.write_artifact_store(
                root,
                manifest_artifacts=[],
                files={
                    "evidence_registry.json": {
                        "metadata": {
                            "artifact_id": "artifact.evidence_registry.fixture_suite.v1"
                        },
                        "entries": [entry],
                    }
                },
            )

            status, response = evidence_response(
                root,
                "validation.checksum.public.customers.v1",
            )

        self.assertEqual(status, 200)
        self.assertEqual(response["entry"], entry)

    def test_evidence_response_returns_404_for_missing_ref(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.write_artifact_store(
                root,
                manifest_artifacts=[],
                files={"evidence_registry.json": {"entries": []}},
            )

            status, response = evidence_response(root, "validation.missing.v1")

        self.assertEqual(status, 404)
        self.assertEqual(response["error"]["code"], "evidence_ref_not_found")

    def test_evidence_response_returns_404_without_registry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            status, response = evidence_response(Path(tmpdir), "validation.missing.v1")

        self.assertEqual(status, 404)
        self.assertEqual(response["error"]["code"], "evidence_registry_not_found")

    def test_latest_workflow_run_response_reads_latest_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow_run = self.write_run_store(root)

            status, response = latest_workflow_run_response(root)

        self.assertEqual(status, 200)
        self.assertEqual(
            response["run_manifest"]["workflow_run_id"],
            workflow_run["workflow_run_id"],
        )
        self.assertEqual(response["workflow_run"], workflow_run)

    def test_workflow_run_response_reads_run_by_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow_run = self.write_run_store(root)

            status, response = workflow_run_response(root, workflow_run["workflow_run_id"])

        self.assertEqual(status, 200)
        self.assertEqual(response["workflow_run"], workflow_run)

    def test_workflow_audit_response_reads_audit_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow_run = self.write_run_store(root)

            status, response = workflow_audit_response(root, workflow_run["workflow_run_id"])

        self.assertEqual(status, 200)
        self.assertEqual(response["workflow_run_id"], workflow_run["workflow_run_id"])
        self.assertEqual(response["event_count"], 1)

    def test_latest_workflow_run_response_returns_404_without_runs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            status, response = latest_workflow_run_response(Path(tmpdir))

        self.assertEqual(status, 404)
        self.assertEqual(response["error"]["code"], "workflow_run_not_found")

    def write_artifact_store(self, root, *, manifest_artifacts, files):
        artifacts = root / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / "manifest.json").write_text(
            json.dumps(
                {
                    "passed": True,
                    "artifact_count": len(manifest_artifacts),
                    "artifacts": manifest_artifacts,
                }
            )
        )
        for relative_path, content in files.items():
            path = artifacts / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(content))

    def write_run_store(self, root):
        workflow_run_id = "workflow.fixture_validation.20260630_120000"
        workflow_run = {
            "workflow_run_id": workflow_run_id,
            "status": "completed",
            "current_stage": "artifacts_written",
        }
        audit_log = {
            "audit_schema_version": "audit_event.v1",
            "workflow_run_id": workflow_run_id,
            "event_count": 1,
            "events": [{"audit_event_id": "audit.workflow.v1"}],
        }
        run_dir = root / "runs" / workflow_run_id
        run_dir.mkdir(parents=True)
        (run_dir / "workflow_run.json").write_text(json.dumps(workflow_run))
        (run_dir / "audit_log.json").write_text(json.dumps(audit_log))
        manifest = {
            "run_store_version": "local_run_store.v1",
            "passed": True,
            "workflow_run_id": workflow_run_id,
            "workflow_run_path": str(run_dir / "workflow_run.json"),
            "audit_log_path": str(run_dir / "audit_log.json"),
            "audit_event_count": 1,
        }
        (root / "runs" / "latest.json").write_text(json.dumps(manifest))
        return workflow_run

    def write_scenario(
        self,
        root,
        scenario_id,
        *,
        description="Demo scenario.",
        critical_tables=None,
    ):
        scenario_dir = root / "fixtures" / "scenarios" / scenario_id
        scenario_dir.mkdir(parents=True)
        (scenario_dir / "scenario.json").write_text(
            json.dumps(
                {
                    "scenario_id": scenario_id,
                    "description": description,
                    "critical_tables": ["customers"] if critical_tables is None else critical_tables,
                    "expected_results": f"fixtures/scenarios/{scenario_id}/expected_findings.json",
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
