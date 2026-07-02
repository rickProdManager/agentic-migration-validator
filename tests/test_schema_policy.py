import unittest

from tools.schema_diff import SchemaDelta
from tools.schema_policy import map_schema_deltas


def delta(delta_type, **kwargs):
    return SchemaDelta(delta_type=delta_type, schema="public", **kwargs)


class SchemaPolicyTest(unittest.TestCase):
    def test_numeric_widening_routes_to_compatibility_advisory(self):
        result = map_schema_deltas(
            [
                delta(
                    "changed_column_type",
                    table="orders",
                    column="total_amount",
                    source={
                        "data_type": "numeric",
                        "type_signature": "numeric(10,2)",
                        "numeric_precision": 10,
                        "numeric_scale": 2,
                    },
                    target={
                        "data_type": "numeric",
                        "type_signature": "numeric(12,4)",
                        "numeric_precision": 12,
                        "numeric_scale": 4,
                    },
                )
            ],
            critical_tables=["orders"],
        )

        finding = result.findings[0]
        self.assertEqual(finding["finding_key"], "schema.type_widened:public.orders:total_amount")
        self.assertEqual(finding["risk_axis"], "compatibility_advisory")
        self.assertEqual(finding["severity"], "low")
        self.assertEqual(finding["gate_effect"], [])
        self.assertEqual(result.follow_up_checks, ())

    def test_numeric_integer_digit_loss_routes_to_integrity_blocker(self):
        result = map_schema_deltas(
            [
                delta(
                    "changed_column_type",
                    table="orders",
                    column="total_amount",
                    source={
                        "data_type": "numeric",
                        "type_signature": "numeric(10,2)",
                        "numeric_precision": 10,
                        "numeric_scale": 2,
                    },
                    target={
                        "data_type": "numeric",
                        "type_signature": "numeric(10,4)",
                        "numeric_precision": 10,
                        "numeric_scale": 4,
                    },
                )
            ],
            critical_tables=["orders"],
        )

        finding = result.findings[0]
        self.assertEqual(finding["finding_key"], "schema.type_narrowed:public.orders:total_amount")
        self.assertEqual(finding["risk_axis"], "migration_integrity")
        self.assertEqual(finding["severity"], "high")
        self.assertEqual(finding["gate_effect"], ["blocks_cutover", "blocks_ready"])
        self.assertTrue(finding["blast_radius"]["critical_path"])

    def test_relaxed_nullability_emits_low_structural_finding_and_data_check(self):
        result = map_schema_deltas(
            [
                delta(
                    "changed_nullability",
                    table="payments",
                    column="method",
                    source={"nullable": False},
                    target={"nullable": True},
                )
            ],
            critical_tables=["payments"],
        )

        finding = result.findings[0]
        check = result.follow_up_checks[0]

        self.assertEqual(finding["finding_key"], "schema.nullability_relaxed:public.payments:method")
        self.assertEqual(finding["risk_axis"], "migration_integrity")
        self.assertEqual(finding["severity"], "low")
        self.assertEqual(finding["gate_effect"], [])
        self.assertEqual(check.check_type, "nulls_in_relaxed_required_column")
        self.assertEqual(check.column, "method")
        self.assertIn(check.evidence_ref, finding["evidence_refs"])

    def test_missing_unique_constraint_emits_structural_finding_and_duplicate_check(self):
        result = map_schema_deltas(
            [
                delta(
                    "missing_unique_constraint",
                    table="payments",
                    constraint="payments_payment_reference_key",
                    source={
                        "name": "payments_payment_reference_key",
                        "constraint_type": "unique",
                        "columns": ["payment_reference"],
                    },
                )
            ]
        )

        finding = result.findings[0]
        check = result.follow_up_checks[0]

        self.assertEqual(
            finding["finding_key"],
            "schema.unique_constraint_relaxed:public.payments:payments_payment_reference_key",
        )
        self.assertEqual(finding["risk_axis"], "migration_integrity")
        self.assertEqual(finding["severity"], "low")
        self.assertEqual(check.check_type, "duplicates_after_unique_relaxation")
        self.assertEqual(check.columns, ("payment_reference",))
        self.assertIn(check.evidence_ref, finding["evidence_refs"])

    def test_missing_foreign_key_emits_structural_finding_and_orphan_check(self):
        result = map_schema_deltas(
            [
                delta(
                    "missing_foreign_key_constraint",
                    table="orders",
                    constraint="orders_customer_id_fkey",
                    source={
                        "name": "orders_customer_id_fkey",
                        "constraint_type": "foreign_key",
                        "columns": ["customer_id"],
                        "referenced_schema": "public",
                        "referenced_table": "customers",
                        "referenced_columns": ["customer_id"],
                    },
                )
            ],
            critical_tables=["orders"],
        )

        finding = result.findings[0]
        check = result.follow_up_checks[0]

        self.assertEqual(
            finding["finding_key"],
            "schema.foreign_key_relaxed:public.orders:orders_customer_id_fkey",
        )
        self.assertEqual(finding["severity"], "low")
        self.assertEqual(finding["gate_effect"], [])
        self.assertEqual(check.check_type, "orphans_after_foreign_key_relaxation")
        self.assertEqual(check.columns, ("customer_id",))
        self.assertEqual(check.referenced_table, "customers")
        self.assertEqual(check.referenced_columns, ("customer_id",))
        self.assertIn(check.evidence_ref, finding["evidence_refs"])

    def test_extra_target_column_routes_to_low_advisory(self):
        result = map_schema_deltas(
            [
                delta(
                    "extra_column",
                    table="subscriptions",
                    column="source_system",
                    target={"data_type": "text"},
                )
            ]
        )

        finding = result.findings[0]
        self.assertEqual(
            finding["finding_key"],
            "schema.extra_target_column:public.subscriptions:source_system",
        )
        self.assertEqual(finding["risk_axis"], "compatibility_advisory")
        self.assertEqual(finding["severity"], "low")
        self.assertEqual(finding["gate_effect"], [])


if __name__ == "__main__":
    unittest.main()
