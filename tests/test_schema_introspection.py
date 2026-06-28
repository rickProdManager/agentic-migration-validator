import unittest

from tools.schema_introspection import database_schema_from_catalog_rows


class SchemaIntrospectionTest(unittest.TestCase):
    def test_builds_stable_schema_model_from_catalog_rows(self):
        schema = database_schema_from_catalog_rows(
            tables=[
                {"table_schema": "public", "table_name": "customers"},
                {"table_schema": "public", "table_name": "orders"},
            ],
            columns=[
                {
                    "table_schema": "public",
                    "table_name": "orders",
                    "column_name": "total_amount",
                    "ordinal_position": 2,
                    "data_type": "numeric",
                    "is_nullable": "NO",
                    "numeric_precision": 10,
                    "numeric_scale": 2,
                },
                {
                    "table_schema": "public",
                    "table_name": "orders",
                    "column_name": "order_id",
                    "ordinal_position": 1,
                    "data_type": "integer",
                    "is_nullable": "NO",
                },
                {
                    "table_schema": "public",
                    "table_name": "customers",
                    "column_name": "customer_id",
                    "ordinal_position": 1,
                    "data_type": "integer",
                    "is_nullable": "NO",
                },
            ],
            constraints=[
                {
                    "table_schema": "public",
                    "table_name": "orders",
                    "constraint_name": "orders_pkey",
                    "constraint_type": "p",
                    "columns": ["order_id"],
                    "definition": "PRIMARY KEY (order_id)",
                },
                {
                    "table_schema": "public",
                    "table_name": "orders",
                    "constraint_name": "orders_customer_id_fkey",
                    "constraint_type": "f",
                    "columns": ["customer_id"],
                    "referenced_schema": "public",
                    "referenced_table": "customers",
                    "referenced_columns": ["customer_id"],
                    "definition": "FOREIGN KEY (customer_id) REFERENCES customers(customer_id)",
                },
            ],
        )

        orders = schema.table_map[("public", "orders")]

        self.assertEqual([column.name for column in orders.columns], ["order_id", "total_amount"])
        self.assertEqual(orders.column_map["total_amount"].type_signature, "numeric(10,2)")
        self.assertFalse(orders.column_map["total_amount"].nullable)
        self.assertEqual(orders.constraint_map["orders_pkey"].constraint_type, "primary_key")
        self.assertEqual(
            orders.constraint_map["orders_customer_id_fkey"].referenced_table,
            "customers",
        )


if __name__ == "__main__":
    unittest.main()
