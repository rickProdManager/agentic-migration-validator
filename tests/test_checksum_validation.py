import unittest
from decimal import Decimal

from tools.checksum import ColumnSpec
from tools.checksum_validation import compare_table_checksum


class ChecksumValidationTest(unittest.TestCase):
    def test_matching_rows_emit_no_finding(self):
        columns = [
            ColumnSpec("customer_id", "integer"),
            ColumnSpec("email", "text"),
            ColumnSpec("full_name", "text"),
        ]
        rows = [
            {
                "customer_id": 1,
                "email": "ada@example.com",
                "full_name": "Ada Lovelace",
            }
        ]

        evidence, finding = compare_table_checksum(
            schema="public",
            table="customers",
            columns=columns,
            source_rows=rows,
            target_rows=rows,
            critical_path=True,
        )

        self.assertTrue(evidence.matched)
        self.assertIsNone(finding)

    def test_content_drift_emits_checksum_mismatch_finding(self):
        columns = [
            ColumnSpec("customer_id", "integer"),
            ColumnSpec("email", "text"),
            ColumnSpec("full_name", "text"),
            ColumnSpec("balance", "numeric", precision=10, scale=2),
        ]

        evidence, finding = compare_table_checksum(
            schema="public",
            table="customers",
            columns=columns,
            source_rows=[
                {
                    "customer_id": 1,
                    "email": "ada@example.com",
                    "full_name": "Ada Lovelace",
                    "balance": Decimal("10.00"),
                }
            ],
            target_rows=[
                {
                    "customer_id": 1,
                    "email": "ada@example.com",
                    "full_name": "Ada L.",
                    "balance": Decimal("10.0"),
                }
            ],
            critical_path=True,
        )

        self.assertFalse(evidence.matched)
        self.assertIsNotNone(finding)
        self.assertEqual(
            finding["finding_key"],
            "validation.checksum_mismatch:public.customers:*",
        )
        self.assertEqual(finding["record_type"], "detector_finding")
        self.assertEqual(finding["risk_axis"], "migration_integrity")
        self.assertEqual(finding["detector"], "canonical_checksum")
        self.assertEqual(finding["severity"], "high")
        self.assertEqual(finding["gate_effect"], ["blocks_cutover", "blocks_ready"])
        self.assertEqual(finding["evidence_refs"], ["validation.checksum.public.customers.v1"])
        self.assertTrue(finding["blast_radius"]["critical_path"])

    def test_target_missing_rows_are_left_to_row_presence_detector(self):
        columns = [
            ColumnSpec("payment_id", "integer"),
            ColumnSpec("payment_reference", "text"),
        ]

        evidence, finding = compare_table_checksum(
            schema="public",
            table="payments",
            columns=columns,
            source_rows=[
                {"payment_id": 5000, "payment_reference": "PAY-100"},
                {"payment_id": 5001, "payment_reference": "PAY-101"},
            ],
            target_rows=[
                {"payment_id": 5000, "payment_reference": "PAY-100"},
            ],
            critical_path=True,
        )

        self.assertFalse(evidence.matched)
        self.assertIsNone(finding)


if __name__ == "__main__":
    unittest.main()
