import importlib
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal


class ChecksumCanonicalizationTest(unittest.TestCase):
    def setUp(self):
        self.checksum = importlib.import_module("tools.checksum")

    def column(self, name, logical_type, **kwargs):
        return self.checksum.ColumnSpec(name=name, logical_type=logical_type, **kwargs)

    def row_digest(self, row, columns):
        return self.checksum.row_digest(row, columns)

    def table_digest(self, rows, columns):
        return self.checksum.table_digest(rows, columns)

    def test_numeric_formatting_does_not_change_hash(self):
        columns = [self.column("amount", "numeric", scale=2)]

        self.assertEqual(
            self.row_digest({"amount": Decimal("10")}, columns),
            self.row_digest({"amount": Decimal("10.00")}, columns),
        )

    def test_numeric_scale_difference_does_not_duplicate_schema_drift(self):
        source_columns = [self.column("amount", "numeric", precision=10, scale=2)]
        target_columns = [self.column("amount", "numeric", precision=10, scale=4)]

        self.assertEqual(
            self.row_digest({"amount": Decimal("10.00")}, source_columns),
            self.row_digest({"amount": Decimal("10.0000")}, target_columns),
        )

    def test_numeric_value_change_hashes_distinctly(self):
        columns = [self.column("amount", "numeric", scale=2)]

        self.assertNotEqual(
            self.row_digest({"amount": Decimal("10.00")}, columns),
            self.row_digest({"amount": Decimal("10.01")}, columns),
        )

    def test_timestamptz_same_instant_hashes_equal_across_time_zones(self):
        columns = [self.column("created_at", "timestamptz")]

        self.assertEqual(
            self.row_digest(
                {"created_at": datetime(2026, 1, 15, 17, 30, tzinfo=timezone.utc)},
                columns,
            ),
            self.row_digest(
                {
                    "created_at": datetime(
                        2026,
                        1,
                        15,
                        9,
                        30,
                        tzinfo=timezone(timedelta(hours=-8)),
                    )
                },
                columns,
            ),
        )

    def test_timestamptz_different_instant_hashes_distinctly(self):
        columns = [self.column("created_at", "timestamptz")]

        self.assertNotEqual(
            self.row_digest(
                {"created_at": datetime(2026, 1, 15, 17, 30, tzinfo=timezone.utc)},
                columns,
            ),
            self.row_digest(
                {"created_at": datetime(2026, 1, 15, 17, 31, tzinfo=timezone.utc)},
                columns,
            ),
        )

    def test_json_object_key_order_does_not_change_hash(self):
        columns = [self.column("payload", "jsonb")]

        self.assertEqual(
            self.row_digest(
                {"payload": {"b": 2, "a": {"z": 9, "y": 8}}},
                columns,
            ),
            self.row_digest(
                {"payload": {"a": {"y": 8, "z": 9}, "b": 2}},
                columns,
            ),
        )

    def test_json_array_order_change_hashes_distinctly(self):
        columns = [self.column("payload", "jsonb")]

        self.assertNotEqual(
            self.row_digest({"payload": {"items": [1, 2, 3]}}, columns),
            self.row_digest({"payload": {"items": [3, 2, 1]}}, columns),
        )

    def test_null_and_empty_string_hash_distinctly(self):
        columns = [self.column("nickname", "text")]

        self.assertNotEqual(
            self.row_digest({"nickname": None}, columns),
            self.row_digest({"nickname": ""}, columns),
        )

    def test_column_order_does_not_change_hash(self):
        row = {"id": 7, "amount": Decimal("12.30")}

        self.assertEqual(
            self.row_digest(
                row,
                [
                    self.column("id", "integer"),
                    self.column("amount", "numeric", scale=2),
                ],
            ),
            self.row_digest(
                row,
                [
                    self.column("amount", "numeric", scale=2),
                    self.column("id", "integer"),
                ],
            ),
        )

    def test_table_digest_is_row_order_independent(self):
        columns = [
            self.column("id", "integer"),
            self.column("amount", "numeric", scale=2),
        ]
        rows = [
            {"id": 1, "amount": Decimal("10.00")},
            {"id": 2, "amount": Decimal("20.00")},
        ]

        self.assertEqual(
            self.table_digest(rows, columns),
            self.table_digest(list(reversed(rows)), columns),
        )

    def test_table_digest_changes_when_content_changes(self):
        columns = [
            self.column("id", "integer"),
            self.column("amount", "numeric", scale=2),
        ]

        self.assertNotEqual(
            self.table_digest(
                [
                    {"id": 1, "amount": Decimal("10.00")},
                    {"id": 2, "amount": Decimal("20.00")},
                ],
                columns,
            ),
            self.table_digest(
                [
                    {"id": 1, "amount": Decimal("10.00")},
                    {"id": 2, "amount": Decimal("21.00")},
                ],
                columns,
            ),
        )


if __name__ == "__main__":
    unittest.main()
