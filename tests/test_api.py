import json
import tempfile
import unittest
from pathlib import Path

from tools.api import health_response, latest_manifest_response, scenarios_response


class ApiTest(unittest.TestCase):
    def test_health_response_reports_version(self):
        response = health_response()

        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["version"], "0.1.0")

    def test_scenarios_response_reads_fixture_manifests(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scenario_dir = root / "fixtures" / "scenarios" / "demo"
            scenario_dir.mkdir(parents=True)
            (scenario_dir / "scenario.json").write_text(
                json.dumps(
                    {
                        "scenario_id": "demo",
                        "description": "Demo scenario.",
                        "critical_tables": ["customers"],
                        "expected_results": "fixtures/scenarios/demo/expected_findings.json",
                    }
                )
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


if __name__ == "__main__":
    unittest.main()
