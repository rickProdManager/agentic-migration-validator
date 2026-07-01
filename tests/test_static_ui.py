import unittest
from pathlib import Path

from scripts.serve_api import (
    LOCAL_ONLY_WARNING,
    MAX_JSON_BODY_BYTES,
    UI_ROOT,
    _content_type,
    _is_cross_site_post,
    _is_relative_to,
    _unexpected_body_response,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class StaticUiTest(unittest.TestCase):
    def test_dashboard_assets_exist(self):
        self.assertTrue((PROJECT_ROOT / "ui" / "index.html").exists())
        self.assertTrue((PROJECT_ROOT / "ui" / "styles.css").exists())
        self.assertTrue((PROJECT_ROOT / "ui" / "app.js").exists())

    def test_dashboard_mounts_expected_elements(self):
        html = (PROJECT_ROOT / "ui" / "index.html").read_text()

        self.assertIn('id="scenario-list"', html)
        self.assertIn('id="run-select"', html)
        self.assertIn('id="launch-form"', html)
        self.assertIn('id="launch-scenario-list"', html)
        self.assertIn('id="launch-submit-button"', html)
        self.assertIn('id="operator-guidance"', html)
        self.assertIn('id="operator-guidance-status"', html)
        self.assertIn('id="result-summary-list"', html)
        self.assertIn('id="workflow-step-list"', html)
        self.assertIn('id="transition-list"', html)
        self.assertIn('id="local-only-warning"', html)
        self.assertIn("Local demo only", html)
        self.assertIn('id="gate-grid"', html)
        self.assertIn('id="approval-state"', html)
        self.assertIn('id="approval-form"', html)
        self.assertIn('id="approval-type-select"', html)
        self.assertIn('id="approval-evidence-select"', html)
        self.assertIn('id="approval-impact"', html)
        self.assertIn('id="approval-confirmation-input"', html)
        self.assertIn('id="approval-review"', html)
        self.assertIn('id="approval-review-list"', html)
        self.assertIn('id="approval-review-cancel-button"', html)
        self.assertIn('id="audit-list"', html)
        self.assertIn('id="runbook-sections"', html)
        self.assertIn('id="runbook-evidence-list"', html)
        self.assertIn('id="evidence-detail"', html)
        self.assertIn('id="audit-detail"', html)

    def test_dashboard_defines_human_readable_runtime_labels(self):
        app_js = (PROJECT_ROOT / "ui" / "app.js").read_text()

        self.assertIn('clean_migration: "Clean Migration"', app_js)
        self.assertIn('schema_drift: "Schema Drift"', app_js)
        self.assertIn('run_deterministic_evals: "Run Deterministic Evaluations"', app_js)
        self.assertIn('artifacts_written: "Artifacts Written"', app_js)
        self.assertIn("function scenarioLabel", app_js)
        self.assertIn("function evidenceLabel", app_js)

    def test_dashboard_defines_operator_error_prevention_affordances(self):
        app_js = (PROJECT_ROOT / "ui" / "app.js").read_text()
        styles = (PROJECT_ROOT / "ui" / "styles.css").read_text()

        self.assertIn("function renderOperatorGuidance", app_js)
        self.assertIn("function renderFirstRunGuidance", app_js)
        self.assertIn("function renderFailedRunGuidance", app_js)
        self.assertIn("function renderApprovalImpact", app_js)
        self.assertIn("function gateNextAction", app_js)
        self.assertIn("function gateBlockerTags", app_js)
        self.assertIn("function impactedGatesForFinding", app_js)
        self.assertIn("function scenarioBlockerSummary", app_js)
        self.assertIn("function syncApprovalSubmitState", app_js)
        self.assertIn("function selectedRunCompleted", app_js)
        self.assertIn("function failedWorkflowStep", app_js)
        self.assertIn("function approvalRemainingBlockers", app_js)
        self.assertIn("function approvalGateEvidenceRef", app_js)
        self.assertIn("function preferredApprovalEvidenceRef", app_js)
        self.assertIn("function renderApprovalReview", app_js)
        self.assertIn("function approvalReviewDetails", app_js)
        self.assertIn("function approvalImpactSummary", app_js)
        self.assertIn("function reviewRow", app_js)
        self.assertIn("evidenceBackedApprovalGates", app_js)
        self.assertIn("reviewingApproval", app_js)
        self.assertIn('"can_recommend_cutover"', app_js)
        self.assertIn('"can_mark_ready"', app_js)
        self.assertIn("gate.${gate}.${selected.scenario_id}.v1", app_js)
        self.assertIn("Gate outputs stay computed", app_js)
        self.assertIn("will remain blocked", app_js)
        self.assertIn("Confirm Review", app_js)
        self.assertIn("Review Approval", app_js)
        self.assertIn("Record Approval", app_js)
        self.assertIn("Does not directly set readiness", app_js)
        self.assertIn("Completed Run Required", app_js)
        self.assertIn("Approvals are disabled for failed or incomplete runs.", app_js)
        self.assertIn("Confirm evidence review before recording approval.", app_js)
        self.assertIn("Blocks:", app_js)
        self.assertIn(".approval-review", styles)
        self.assertIn(".secondary-button", styles)
        self.assertIn(".guidance-step.blocked", styles)
        self.assertIn(".blocker-tag.blocked", styles)
        self.assertIn(".blocker-tag.warn", styles)
        self.assertIn(".approval-impact.blocked", styles)
        self.assertIn(".approval-confirmation", styles)

    def test_static_content_types(self):
        self.assertEqual(_content_type(UI_ROOT / "index.html"), "text/html; charset=utf-8")
        self.assertEqual(_content_type(UI_ROOT / "styles.css"), "text/css; charset=utf-8")
        self.assertEqual(_content_type(UI_ROOT / "app.js"), "application/javascript; charset=utf-8")

    def test_static_path_guard_rejects_parent_escape(self):
        self.assertTrue(_is_relative_to((UI_ROOT / "index.html").resolve(), UI_ROOT.resolve()))
        self.assertFalse(_is_relative_to(PROJECT_ROOT / "README.md", UI_ROOT.resolve()))

    def test_cross_site_post_guard_rejects_browser_cross_origin_posts(self):
        self.assertTrue(
            _is_cross_site_post(
                "https://example.com",
                "127.0.0.1:8080",
                "cross-site",
            )
        )
        self.assertTrue(_is_cross_site_post("null", "127.0.0.1:8080", None))
        self.assertFalse(
            _is_cross_site_post(
                "http://127.0.0.1:8080",
                "127.0.0.1:8080",
                "same-origin",
            )
        )
        self.assertFalse(_is_cross_site_post(None, "127.0.0.1:8080", None))

    def test_local_api_json_body_limit_is_defined(self):
        self.assertEqual(MAX_JSON_BODY_BYTES, 64 * 1024)

    def test_workflow_run_endpoint_rejects_unexpected_body(self):
        self.assertIsNone(_unexpected_body_response(None))
        self.assertIsNone(_unexpected_body_response("0"))

        status, payload = _unexpected_body_response("8")

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "unexpected_request_body")

    def test_workflow_run_endpoint_rejects_bad_or_oversized_content_length(self):
        status, payload = _unexpected_body_response("not-an-int")

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "invalid_content_length")

        status, payload = _unexpected_body_response(str(MAX_JSON_BODY_BYTES + 1))

        self.assertEqual(status, 413)
        self.assertEqual(payload["error"]["code"], "request_body_too_large")

    def test_local_api_startup_warning_is_defined(self):
        self.assertIn("Local demo only", LOCAL_ONLY_WARNING)
        self.assertIn("127.0.0.1", LOCAL_ONLY_WARNING)
        self.assertIn("do not expose", LOCAL_ONLY_WARNING)


if __name__ == "__main__":
    unittest.main()
