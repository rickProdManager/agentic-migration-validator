import unittest
from datetime import datetime, timezone

from tools.row_validation import compare_table_row_presence


SOURCE_PAYMENTS = [
    {
        "payment_id": 5000,
        "payment_reference": "PAY-100",
        "paid_at": datetime(2026, 2, 1, 10, 25, tzinfo=timezone.utc),
    },
    {
        "payment_id": 5001,
        "payment_reference": "PAY-101",
        "paid_at": datetime(2026, 2, 2, 14, 40, tzinfo=timezone.utc),
    },
]


class RowValidationTest(unittest.TestCase):
    def test_matching_primary_keys_emit_no_finding(self):
        evidence, finding = compare_table_row_presence(
            schema="public",
            table="payments",
            primary_key_columns=["payment_id"],
            source_rows=SOURCE_PAYMENTS,
            target_rows=SOURCE_PAYMENTS,
            critical_path=True,
        )

        self.assertEqual(evidence.missing_source_row_count, 0)
        self.assertIsNone(finding)

    def test_unexplained_missing_source_rows_emit_blocking_missing_rows(self):
        evidence, finding = compare_table_row_presence(
            schema="public",
            table="payments",
            primary_key_columns=["payment_id"],
            source_rows=SOURCE_PAYMENTS,
            target_rows=[SOURCE_PAYMENTS[0]],
            critical_path=True,
        )

        self.assertEqual(evidence.missing_source_row_count, 1)
        self.assertEqual(evidence.unexplained_missing_row_count, 1)
        self.assertIsNotNone(finding)
        self.assertEqual(
            finding["finding_key"],
            "validation.missing_rows:public.payments:*",
        )
        self.assertEqual(finding["finding_type"], "validation.missing_rows")
        self.assertEqual(finding["detector"], "row_presence")
        self.assertEqual(finding["severity"], "high")
        self.assertEqual(finding["gate_effect"], ["blocks_cutover", "blocks_ready"])

    def test_missing_rows_after_known_cutoff_emit_non_blocking_replication_lag(self):
        evidence, finding = compare_table_row_presence(
            schema="public",
            table="payments",
            primary_key_columns=["payment_id"],
            source_rows=SOURCE_PAYMENTS,
            target_rows=[SOURCE_PAYMENTS[0]],
            lag_policy={
                "freshness_column": "paid_at",
                "source_cutoff": "2026-02-02T00:00:00Z",
            },
            critical_path=True,
        )

        self.assertEqual(evidence.missing_source_row_count, 1)
        self.assertEqual(evidence.explained_lag_row_count, 1)
        self.assertEqual(evidence.unexplained_missing_row_count, 0)
        self.assertIsNotNone(finding)
        self.assertEqual(
            finding["finding_key"],
            "validation.replication_lag:public.payments:*",
        )
        self.assertEqual(finding["finding_type"], "validation.replication_lag")
        self.assertEqual(finding["detector"], "lag_aware_row_freshness")
        self.assertEqual(finding["severity"], "info")
        self.assertEqual(finding["gate_effect"], [])

    def test_rows_missing_before_known_cutoff_remain_missing_rows(self):
        evidence, finding = compare_table_row_presence(
            schema="public",
            table="payments",
            primary_key_columns=["payment_id"],
            source_rows=SOURCE_PAYMENTS,
            target_rows=[SOURCE_PAYMENTS[1]],
            lag_policy={
                "freshness_column": "paid_at",
                "source_cutoff": "2026-02-02T00:00:00Z",
            },
            critical_path=True,
        )

        self.assertEqual(evidence.explained_lag_row_count, 0)
        self.assertEqual(evidence.unexplained_missing_row_count, 1)
        self.assertIsNotNone(finding)
        self.assertEqual(finding["finding_type"], "validation.missing_rows")


if __name__ == "__main__":
    unittest.main()
