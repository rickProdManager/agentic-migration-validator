import unittest
from pathlib import Path

from scripts.serve_api import UI_ROOT, _content_type, _is_relative_to


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
        self.assertIn('id="result-summary-list"', html)
        self.assertIn('id="workflow-step-list"', html)
        self.assertIn('id="transition-list"', html)
        self.assertIn('id="gate-grid"', html)
        self.assertIn('id="approval-state"', html)
        self.assertIn('id="approval-form"', html)
        self.assertIn('id="approval-type-select"', html)
        self.assertIn('id="approval-evidence-select"', html)
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

    def test_static_content_types(self):
        self.assertEqual(_content_type(UI_ROOT / "index.html"), "text/html; charset=utf-8")
        self.assertEqual(_content_type(UI_ROOT / "styles.css"), "text/css; charset=utf-8")
        self.assertEqual(_content_type(UI_ROOT / "app.js"), "application/javascript; charset=utf-8")

    def test_static_path_guard_rejects_parent_escape(self):
        self.assertTrue(_is_relative_to((UI_ROOT / "index.html").resolve(), UI_ROOT.resolve()))
        self.assertFalse(_is_relative_to(PROJECT_ROOT / "README.md", UI_ROOT.resolve()))


if __name__ == "__main__":
    unittest.main()
