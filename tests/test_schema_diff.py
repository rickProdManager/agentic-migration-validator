import unittest

from tools.schema_diff import diff_database_schemas
from tools.schema_introspection import (
    ColumnSchema,
    ConstraintSchema,
    DatabaseSchema,
    TableSchema,
)


def database(*tables):
    return DatabaseSchema(tables=tables)


def table(name, *, columns=(), constraints=()):
    return TableSchema(schema="public", name=name, columns=columns, constraints=constraints)


def column(name, data_type="text", *, nullable=False, precision=None, scale=None):
    return ColumnSchema(
        name=name,
        data_type=data_type,
        nullable=nullable,
        ordinal_position=1,
        numeric_precision=precision,
        numeric_scale=scale,
    )


def constraint(name, constraint_type, columns):
    return ConstraintSchema(
        name=name,
        constraint_type=constraint_type,
        columns=tuple(columns),
        definition=f"{constraint_type}:{','.join(columns)}",
    )


class SchemaDiffTest(unittest.TestCase):
    def test_identical_schemas_emit_no_deltas(self):
        source = database(table("customers", columns=(column("email"),)))
        target = database(table("customers", columns=(column("email"),)))

        self.assertEqual(diff_database_schemas(source, target), ())

    def test_reports_missing_and_extra_tables(self):
        deltas = diff_database_schemas(
            database(table("customers")),
            database(table("orders")),
        )

        self.assertEqual(
            [delta.delta_type for delta in deltas],
            ["missing_table", "extra_table"],
        )
        self.assertEqual(deltas[0].table, "customers")
        self.assertEqual(deltas[1].table, "orders")

    def test_reports_missing_and_extra_columns(self):
        deltas = diff_database_schemas(
            database(table("customers", columns=(column("email"),))),
            database(table("customers", columns=(column("full_name"),))),
        )

        self.assertEqual(
            [delta.delta_type for delta in deltas],
            ["missing_column", "extra_column"],
        )
        self.assertEqual(deltas[0].column, "email")
        self.assertEqual(deltas[1].column, "full_name")

    def test_reports_numeric_type_signature_change(self):
        deltas = diff_database_schemas(
            database(
                table(
                    "orders",
                    columns=(column("total_amount", "numeric", precision=10, scale=2),),
                )
            ),
            database(
                table(
                    "orders",
                    columns=(column("total_amount", "numeric", precision=10, scale=4),),
                )
            ),
        )

        self.assertEqual(len(deltas), 1)
        self.assertEqual(deltas[0].delta_type, "changed_column_type")
        self.assertEqual(deltas[0].source["type_signature"], "numeric(10,2)")
        self.assertEqual(deltas[0].target["type_signature"], "numeric(10,4)")

    def test_reports_nullability_change(self):
        deltas = diff_database_schemas(
            database(table("payments", columns=(column("method", nullable=False),))),
            database(table("payments", columns=(column("method", nullable=True),))),
        )

        self.assertEqual(len(deltas), 1)
        self.assertEqual(deltas[0].delta_type, "changed_nullability")
        self.assertEqual(deltas[0].source, {"nullable": False})
        self.assertEqual(deltas[0].target, {"nullable": True})

    def test_reports_missing_unique_constraint(self):
        deltas = diff_database_schemas(
            database(
                table(
                    "payments",
                    constraints=(
                        constraint(
                            "payments_payment_reference_key",
                            "unique",
                            ["payment_reference"],
                        ),
                    ),
                )
            ),
            database(table("payments")),
        )

        self.assertEqual(len(deltas), 1)
        self.assertEqual(deltas[0].delta_type, "missing_unique_constraint")
        self.assertEqual(deltas[0].constraint, "payments_payment_reference_key")

    def test_reports_changed_foreign_key_signature(self):
        source = ConstraintSchema(
            name="orders_customer_id_fkey",
            constraint_type="foreign_key",
            columns=("customer_id",),
            referenced_schema="public",
            referenced_table="customers",
            referenced_columns=("customer_id",),
        )
        target = ConstraintSchema(
            name="orders_customer_id_fkey",
            constraint_type="foreign_key",
            columns=("customer_id",),
            referenced_schema="public",
            referenced_table="legacy_customers",
            referenced_columns=("customer_id",),
        )

        deltas = diff_database_schemas(
            database(table("orders", constraints=(source,))),
            database(table("orders", constraints=(target,))),
        )

        self.assertEqual(len(deltas), 1)
        self.assertEqual(deltas[0].delta_type, "changed_foreign_key_constraint")
        self.assertEqual(deltas[0].target["referenced_table"], "legacy_customers")


if __name__ == "__main__":
    unittest.main()
