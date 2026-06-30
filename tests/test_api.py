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
    submit_workflow_approval_response,
    validate_requested_scenarios,
    workflow_run_failed_response,
    workflow_audit_response,
    workflow_approvals_response,
    workflow_artifact_response,
    workflow_evidence_response,
    workflow_readiness_response,
    workflow_run_response,
    workflow_runs_response,
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

    def test_workflow_run_failed_response_is_json_contract(self):
        status, response = workflow_run_failed_response(ConnectionError("database unavailable"))

        self.assertEqual(status, 500)
        self.assertEqual(response["error"]["code"], "workflow_run_failed")
        self.assertIn("Docker fixture containers", response["error"]["message"])
        self.assertEqual(response["error"]["details"]["exception"], "ConnectionError")
        self.assertNotIn("message", response["error"]["details"])
        self.assertIn("make db-up", response["error"]["details"]["recovery_hint"])

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

    def test_workflow_runs_response_lists_persisted_runs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow_run = self.write_run_store(root)

            status, response = workflow_runs_response(root)

        self.assertEqual(status, 200)
        self.assertEqual(response["run_count"], 1)
        self.assertEqual(response["latest_workflow_run_id"], workflow_run["workflow_run_id"])
        self.assertEqual(response["runs"][0]["workflow_run_id"], workflow_run["workflow_run_id"])
        self.assertTrue(response["runs"][0]["is_latest"])

    def test_workflow_run_response_reads_run_by_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow_run = self.write_run_store(root)

            status, response = workflow_run_response(root, workflow_run["workflow_run_id"])

        self.assertEqual(status, 200)
        self.assertEqual(response["workflow_run"], workflow_run)

    def test_workflow_artifact_response_uses_selected_run_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow_run = self.write_run_store(root)

            status, response = workflow_artifact_response(
                root,
                workflow_run["workflow_run_id"],
                "artifact.runbook_draft.clean_migration.v1",
            )

        self.assertEqual(status, 200)
        self.assertEqual(response["metadata"]["artifact_type"], "runbook")
        self.assertEqual(response["content"]["title"], "Runbook")

    def test_workflow_evidence_response_uses_selected_run_registry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow_run = self.write_run_store(root)

            status, response = workflow_evidence_response(
                root,
                workflow_run["workflow_run_id"],
                "validation.checksum.public.customers.v1",
            )

        self.assertEqual(status, 200)
        self.assertEqual(
            response["entry"]["source_artifact_id"],
            "artifact.eval_report.fixture_suite.v1",
        )

    def test_workflow_audit_response_reads_audit_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow_run = self.write_run_store(root)

            status, response = workflow_audit_response(root, workflow_run["workflow_run_id"])

        self.assertEqual(status, 200)
        self.assertEqual(response["workflow_run_id"], workflow_run["workflow_run_id"])
        self.assertEqual(response["event_count"], 1)

    def test_workflow_approvals_response_reads_approval_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow_run = self.write_run_store(root)

            status, response = workflow_approvals_response(
                root,
                workflow_run["workflow_run_id"],
            )

        self.assertEqual(status, 200)
        self.assertEqual(response["approval_count"], 0)
        self.assertIn("validation_acceptance", response["pending_approvals"])

    def test_submit_workflow_approval_response_persists_approval(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow_run = self.write_run_store(root)

            status, response = submit_workflow_approval_response(
                root,
                workflow_run["workflow_run_id"],
                {
                    "gate": "can_accept_validation",
                    "actor": "human.reviewer",
                    "decision": "approved",
                    "evidence_refs": ["artifact.eval_report.fixture_suite.v1"],
                    "notes": "Reviewed validation artifacts.",
                },
            )
            _, approvals = workflow_approvals_response(root, workflow_run["workflow_run_id"])
            _, audit_log = workflow_audit_response(root, workflow_run["workflow_run_id"])

        self.assertEqual(status, 201)
        self.assertEqual(response["approval"]["approval_type"], "validation_acceptance")
        self.assertEqual(response["run_state"]["approval_count"], 1)
        self.assertEqual(approvals["effective_approvals"], ["validation_acceptance"])
        self.assertEqual(audit_log["event_count"], 2)

    def test_submit_workflow_approval_response_rejects_invalid_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow_run = self.write_run_store(root)

            status, response = submit_workflow_approval_response(
                root,
                workflow_run["workflow_run_id"],
                {
                    "gate": "missing_gate",
                    "actor": "human.reviewer",
                    "decision": "approved",
                    "evidence_refs": ["artifact.eval_report.fixture_suite.v1"],
                },
            )

        self.assertEqual(status, 400)
        self.assertEqual(response["error"]["code"], "invalid_approval")

    def test_workflow_readiness_response_recomputes_gates_from_approvals(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow_run = self.write_run_store(root)

            status, before = workflow_readiness_response(root, workflow_run["workflow_run_id"])
            submit_workflow_approval_response(
                root,
                workflow_run["workflow_run_id"],
                {
                    "gate": "can_accept_validation",
                    "actor": "human.reviewer",
                    "decision": "approved",
                    "evidence_refs": ["artifact.eval_report.fixture_suite.v1"],
                },
            )
            status_after, after = workflow_readiness_response(root, workflow_run["workflow_run_id"])

        before_scenario = before["scenarios"][0]
        after_scenario = after["scenarios"][0]
        self.assertEqual(status, 200)
        self.assertEqual(status_after, 200)
        self.assertFalse(before_scenario["gate_results"]["can_accept_validation"]["allowed"])
        self.assertTrue(after_scenario["gate_results"]["can_accept_validation"]["allowed"])
        self.assertIn(
            "validation_acceptance",
            after["approval_state"]["effective_approvals"],
        )

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
        scenario_id = "clean_migration"
        artifact_dir = root / "artifacts"
        artifact_dir.mkdir()
        eval_report_path = artifact_dir / "eval_report.json"
        runbook_path = artifact_dir / "runbook.json"
        evidence_registry_path = artifact_dir / "evidence_registry.json"
        eval_report_path.write_text(
            json.dumps(
                {
                    "scenarios": [
                        {
                            "scenario_id": scenario_id,
                            "validation_findings": [],
                            "schema_findings": [],
                        }
                    ]
                }
            )
        )
        runbook_path.write_text(
            json.dumps(
                {
                    "metadata": {
                        "artifact_id": f"artifact.runbook_draft.{scenario_id}.v1",
                        "artifact_type": "runbook",
                        "status": "draft",
                    },
                    "title": "Runbook",
                    "sections": [],
                    "claims": [],
                }
            )
        )
        evidence_registry_path.write_text(
            json.dumps(
                {
                    "metadata": {
                        "artifact_id": "artifact.evidence_registry.fixture_suite.v1",
                        "artifact_type": "evidence_registry",
                    },
                    "entries": [
                        {
                            "evidence_ref": "validation.checksum.public.customers.v1",
                            "source_artifact_id": "artifact.eval_report.fixture_suite.v1",
                            "source_artifact_path": "eval_report.json",
                            "source_type": "validation_result",
                            "producer": "eval_runner",
                            "stage": "validation",
                            "content_hash": "sha256:abc",
                        }
                    ],
                }
            )
        )
        artifact_manifest = {
            "passed": True,
            "artifact_count": 3,
            "artifacts": [
                {
                    "artifact_id": "artifact.eval_report.fixture_suite.v1",
                    "path": str(eval_report_path),
                    "content_hash": "sha256:abc",
                },
                {
                    "artifact_id": f"artifact.runbook_draft.{scenario_id}.v1",
                    "path": str(runbook_path),
                    "content_hash": "sha256:def",
                },
                {
                    "artifact_id": "artifact.evidence_registry.fixture_suite.v1",
                    "path": str(evidence_registry_path),
                    "content_hash": "sha256:ghi",
                },
            ],
        }
        workflow_run = {
            "workflow_run_id": workflow_run_id,
            "workflow_version": "fixture_validation_workflow.v1",
            "workspace_id": "workspace_demo",
            "status": "completed",
            "current_stage": "artifacts_written",
            "model_calls": "disabled",
            "scenario_ids": [scenario_id],
            "started_at": "2026-06-30T12:00:00Z",
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
            "artifact_manifest": artifact_manifest,
        }
        audit_log = {
            "audit_schema_version": "audit_event.v1",
            "workflow_run_id": workflow_run_id,
            "event_count": 1,
            "events": [
                {
                    "audit_event_id": "audit.workflow.v1",
                    "audit_schema_version": "audit_event.v1",
                    "workflow_run_id": workflow_run_id,
                    "workspace_id": "workspace_demo",
                    "scenario_id": scenario_id,
                    "created_at": "2026-06-30T12:01:00Z",
                    "actor_name": "workflow_orchestrator",
                    "actor_type": "system",
                    "stage": "artifact_store",
                    "decision": "stage_completed",
                    "status": "completed",
                    "evidence_refs": [],
                    "finding_keys": [],
                    "artifact_ids": [],
                }
            ],
        }
        approval_log = {
            "approval_schema_version": "approval_record.v1",
            "workflow_run_id": workflow_run_id,
            "approval_count": 0,
            "effective_approvals": [],
            "pending_approvals": [
                "cutover_recommendation",
                "final_planning",
                "ready",
                "rollback_recommendation",
                "validation_acceptance",
            ],
            "approvals": [],
        }
        run_dir = root / "runs" / workflow_run_id
        run_dir.mkdir(parents=True)
        (run_dir / "workflow_run.json").write_text(json.dumps(workflow_run))
        (run_dir / "audit_log.json").write_text(json.dumps(audit_log))
        (run_dir / "approvals.json").write_text(json.dumps(approval_log))
        manifest = {
            "run_store_version": "local_run_store.v1",
            "passed": True,
            "workflow_run_id": workflow_run_id,
            "workflow_run_path": str(run_dir / "workflow_run.json"),
            "audit_log_path": str(run_dir / "audit_log.json"),
            "approvals_path": str(run_dir / "approvals.json"),
            "audit_event_count": 1,
            "approval_count": 0,
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
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
