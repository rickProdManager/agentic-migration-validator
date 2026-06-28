import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_ROOT = PROJECT_ROOT / "fixtures" / "scenarios"


class FixtureManifestTest(unittest.TestCase):
    def load_json(self, path):
        return json.loads(path.read_text())

    def test_scenario_declared_files_exist(self):
        for scenario_path in sorted(SCENARIOS_ROOT.glob("*/scenario.json")):
            with self.subTest(scenario=scenario_path.parent.name):
                scenario = self.load_json(scenario_path)

                for key in ("source_seed", "target_seed", "expected_results"):
                    declared_path = PROJECT_ROOT / scenario[key]
                    self.assertTrue(declared_path.exists(), f"{key} does not exist: {declared_path}")

    def test_clean_migration_expects_no_integrity_findings(self):
        expected = self.load_json(
            SCENARIOS_ROOT / "clean_migration" / "expected_findings.json"
        )

        self.assertEqual(expected["scenario_id"], "clean_migration")
        self.assertEqual(expected["model_calls"], "disabled")
        self.assertEqual(expected["expected_findings"], [])

    def test_failed_checksum_expects_customer_checksum_mismatch(self):
        expected = self.load_json(
            SCENARIOS_ROOT / "failed_checksum" / "expected_findings.json"
        )
        finding = expected["expected_findings"][0]

        self.assertEqual(expected["scenario_id"], "failed_checksum")
        self.assertEqual(finding["record_type"], "detector_finding")
        self.assertEqual(finding["risk_axis"], "migration_integrity")
        self.assertEqual(
            finding["finding_key"],
            "validation.checksum_mismatch:public.customers:*",
        )
        self.assertEqual(finding["detector"], "canonical_checksum")
        self.assertEqual(finding["expected_gate_effect"], ["blocks_cutover", "blocks_ready"])

    def test_failed_checksum_target_is_content_only_drift(self):
        target_sql = (SCENARIOS_ROOT / "failed_checksum" / "target.sql").read_text()

        self.assertIn("/fixtures/base/common.sql", target_sql)
        self.assertIn("UPDATE customers", target_sql)
        self.assertIn("full_name = 'Ada L.'", target_sql)

    def test_schema_drift_declares_raw_expected_deltas(self):
        expected = self.load_json(
            SCENARIOS_ROOT / "schema_drift" / "expected_findings.json"
        )
        finding_keys = {finding["finding_key"] for finding in expected["expected_findings"]}
        deltas = {
            (
                delta["delta_type"],
                delta["schema"],
                delta.get("table"),
                delta.get("column"),
                delta.get("constraint"),
            )
            for delta in expected["expected_schema_deltas"]
        }

        self.assertEqual(expected["scenario_id"], "schema_drift")
        self.assertEqual(
            finding_keys,
            {
                "schema.type_widened:public.orders:total_amount",
                "schema.nullability_relaxed:public.payments:method",
                "schema.unique_constraint_relaxed:public.payments:payments_payment_reference_key",
                "schema.extra_target_column:public.subscriptions:source_system",
            },
        )
        self.assertEqual(
            deltas,
            {
                ("changed_column_type", "public", "orders", "total_amount", None),
                ("changed_nullability", "public", "payments", "method", None),
                (
                    "missing_unique_constraint",
                    "public",
                    "payments",
                    None,
                    "payments_payment_reference_key",
                ),
                ("extra_column", "public", "subscriptions", "source_system", None),
            },
        )

    def test_schema_drift_target_is_schema_only_drift(self):
        target_sql = (SCENARIOS_ROOT / "schema_drift" / "target.sql").read_text()

        self.assertIn("/fixtures/base/common.sql", target_sql)
        self.assertIn("DROP CONSTRAINT payments_payment_reference_key", target_sql)
        self.assertIn("ALTER COLUMN method DROP NOT NULL", target_sql)
        self.assertIn("TYPE numeric(12, 4)", target_sql)
        self.assertIn("ADD COLUMN source_system text", target_sql)


if __name__ == "__main__":
    unittest.main()
