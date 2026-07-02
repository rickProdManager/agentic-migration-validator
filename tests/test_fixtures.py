import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_ROOT = PROJECT_ROOT / "fixtures" / "scenarios"


class FixtureManifestTest(unittest.TestCase):
    def load_json(self, path):
        return json.loads(path.read_text())

    def test_docker_fixture_ports_bind_to_localhost(self):
        compose = (PROJECT_ROOT / "docker-compose.yml").read_text()

        self.assertIn('"127.0.0.1:55432:5432"', compose)
        self.assertIn('"127.0.0.1:55433:5432"', compose)
        self.assertNotIn('"55432:5432"', compose)
        self.assertNotIn('"55433:5432"', compose)

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

    def test_missing_rows_declares_blocking_row_presence_finding(self):
        expected = self.load_json(
            SCENARIOS_ROOT / "missing_rows" / "expected_findings.json"
        )
        finding = expected["expected_findings"][0]

        self.assertEqual(expected["scenario_id"], "missing_rows")
        self.assertEqual(
            finding["finding_key"],
            "validation.missing_rows:public.payments:*",
        )
        self.assertEqual(finding["detector"], "row_presence")
        self.assertEqual(finding["expected_gate_effect"], ["blocks_cutover", "blocks_ready"])

    def test_replication_lag_declares_non_blocking_lag_finding(self):
        scenario = self.load_json(SCENARIOS_ROOT / "replication_lag" / "scenario.json")
        expected = self.load_json(
            SCENARIOS_ROOT / "replication_lag" / "expected_findings.json"
        )
        finding = expected["expected_findings"][0]

        self.assertEqual(expected["scenario_id"], "replication_lag")
        self.assertEqual(scenario["allowed_lag"]["table"], "payments")
        self.assertEqual(scenario["allowed_lag"]["freshness_column"], "paid_at")
        self.assertEqual(
            finding["finding_key"],
            "validation.replication_lag:public.payments:*",
        )
        self.assertEqual(finding["detector"], "lag_aware_row_freshness")
        self.assertEqual(finding["expected_gate_effect"], [])

    def test_missing_rows_and_replication_lag_share_same_row_delta(self):
        missing_sql = (SCENARIOS_ROOT / "missing_rows" / "target.sql").read_text()
        lag_sql = (SCENARIOS_ROOT / "replication_lag" / "target.sql").read_text()

        self.assertEqual(missing_sql, lag_sql)
        self.assertIn("DELETE FROM payments", missing_sql)
        self.assertIn("payment_id = 5001", missing_sql)

    def test_broken_fk_declares_referential_findings(self):
        expected = self.load_json(
            SCENARIOS_ROOT / "broken_fk" / "expected_findings.json"
        )
        finding_keys = {finding["finding_key"] for finding in expected["expected_findings"]}
        data_checks = {
            (
                check["check_type"],
                check["schema"],
                check["table"],
                check.get("constraint"),
                check.get("orphan_count"),
            )
            for check in expected["expected_data_checks"]
        }

        self.assertEqual(expected["scenario_id"], "broken_fk")
        self.assertEqual(
            finding_keys,
            {
                "validation.checksum_mismatch:public.orders:*",
                "schema.foreign_key_relaxed:public.orders:orders_customer_id_fkey",
                "validation.broken_referential_integrity:public.orders:orders_customer_id_fkey",
            },
        )
        self.assertEqual(
            data_checks,
            {
                (
                    "orphans_after_foreign_key_relaxation",
                    "public",
                    "orders",
                    "orders_customer_id_fkey",
                    1,
                ),
            },
        )

    def test_broken_fk_target_drops_fk_and_orphans_order(self):
        target_sql = (SCENARIOS_ROOT / "broken_fk" / "target.sql").read_text()

        self.assertIn("/fixtures/base/common.sql", target_sql)
        self.assertIn("DROP CONSTRAINT orders_customer_id_fkey", target_sql)
        self.assertIn("UPDATE orders", target_sql)
        self.assertIn("customer_id = 999", target_sql)
        self.assertIn("order_id = 102", target_sql)

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

    def test_schema_relaxed_unique_violation_declares_escalation_findings(self):
        expected = self.load_json(
            SCENARIOS_ROOT / "schema_relaxed_unique_violation" / "expected_findings.json"
        )
        finding_keys = {finding["finding_key"] for finding in expected["expected_findings"]}
        data_checks = {
            (
                check["check_type"],
                check["schema"],
                check["table"],
                check.get("constraint"),
                check.get("duplicate_group_count"),
            )
            for check in expected["expected_data_checks"]
        }

        self.assertEqual(expected["scenario_id"], "schema_relaxed_unique_violation")
        self.assertEqual(
            finding_keys,
            {
                "validation.checksum_mismatch:public.payments:*",
                "schema.unique_constraint_relaxed:public.payments:payments_payment_reference_key",
                "validation.duplicate_values_after_unique_relaxation:public.payments:payments_payment_reference_key",
            },
        )
        self.assertEqual(
            data_checks,
            {
                (
                    "duplicates_after_unique_relaxation",
                    "public",
                    "payments",
                    "payments_payment_reference_key",
                    1,
                ),
            },
        )

    def test_schema_relaxed_unique_violation_target_drops_unique_and_duplicates_data(self):
        target_sql = (
            SCENARIOS_ROOT / "schema_relaxed_unique_violation" / "target.sql"
        ).read_text()

        self.assertIn("/fixtures/base/common.sql", target_sql)
        self.assertIn("DROP CONSTRAINT payments_payment_reference_key", target_sql)
        self.assertIn("UPDATE payments", target_sql)
        self.assertIn("payment_reference = 'PAY-100'", target_sql)
        self.assertIn("payment_id = 5001", target_sql)


if __name__ == "__main__":
    unittest.main()
