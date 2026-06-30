import unittest

from scripts.smoke_api import run_smoke


class ApiSmokeTest(unittest.TestCase):
    def test_run_smoke_checks_lightweight_routes(self):
        result = run_smoke(
            "http://api.test",
            request_json=self.fake_request,
        )

        self.assertTrue(result["passed"])
        self.assertEqual(
            [check["name"] for check in result["checks"]],
            ["health", "scenarios", "unknown_scenario"],
        )

    def test_run_smoke_checks_workflow_artifact_and_evidence_routes(self):
        result = run_smoke(
            "http://api.test",
            workflow_scenario="failed_checksum",
            request_json=self.fake_request,
        )

        self.assertTrue(result["passed"])
        self.assertEqual(
            [check["name"] for check in result["checks"]],
            [
                "health",
                "scenarios",
                "unknown_scenario",
                "workflow_run",
                "workflow_latest",
                "workflow_runs",
                "workflow_audit",
                "artifact_retrieval",
                "approval_submission",
                "approval_retrieval",
                "approval_aware_readiness",
                "evidence_retrieval",
            ],
        )

    def fake_request(self, method, url, payload=None):
        if method == "GET" and url == "http://api.test/health":
            return 200, {"status": "ok", "version": "0.1.0"}
        if method == "GET" and url == "http://api.test/scenarios":
            return 200, {"scenarios": [{"scenario_id": "failed_checksum"}]}
        if method == "POST" and "missing_scenario" in url:
            return 400, {"error": {"code": "unknown_scenario"}}
        if method == "POST" and "failed_checksum" in url:
            return (
                200,
                {
                    "workflow_run_id": "workflow.fixture_validation.20260630_120000",
                    "status": "completed",
                    "workflow_validation": {"passed": True},
                    "artifact_manifest": {"passed": True, "artifact_count": 3},
                },
            )
        if method == "GET" and url == "http://api.test/workflows/latest":
            return (
                200,
                {
                    "run_manifest": {
                        "workflow_run_id": "workflow.fixture_validation.20260630_120000"
                    }
                },
            )
        if method == "GET" and url == "http://api.test/workflows":
            return (
                200,
                {
                    "run_count": 1,
                    "latest_workflow_run_id": "workflow.fixture_validation.20260630_120000",
                    "runs": [
                        {
                            "workflow_run_id": "workflow.fixture_validation.20260630_120000",
                            "is_latest": True,
                        }
                    ],
                },
            )
        if method == "GET" and url.endswith("/audit"):
            return (
                200,
                {
                    "workflow_run_id": "workflow.fixture_validation.20260630_120000",
                    "event_count": 4,
                    "events": [],
                },
            )
        if method == "POST" and url.endswith("/approvals"):
            self.assertEqual(payload["gate"], "can_accept_validation")
            return (
                201,
                {
                    "approval": {"approval_type": "validation_acceptance"},
                    "effective_approvals": ["validation_acceptance"],
                },
            )
        if method == "GET" and url.endswith("/approvals"):
            return (
                200,
                {
                    "approval_count": 1,
                    "effective_approvals": ["validation_acceptance"],
                    "pending_approvals": [],
                },
            )
        if method == "GET" and url.endswith("/readiness"):
            return (
                200,
                {
                    "approval_state": {
                        "effective_approvals": ["validation_acceptance"]
                    },
                    "scenario_count": 1,
                    "scenarios": [
                        {
                            "gate_results": {
                                "can_accept_validation": {"allowed": True},
                                "can_recommend_cutover": {"allowed": False},
                            }
                        }
                    ],
                },
            )
        if method == "GET" and "/artifacts/" in url:
            return 200, {"artifact_id": "artifact.runbook_draft.failed_checksum.v1"}
        if method == "GET" and "/evidence/" in url:
            return (
                200,
                {
                    "evidence_ref": "validation.checksum.public.customers.v1",
                    "entry": {
                        "source_artifact_id": "artifact.eval_report.fixture_suite.v1"
                    },
                },
            )
        raise AssertionError(f"Unexpected request: {method} {url}")


if __name__ == "__main__":
    unittest.main()
