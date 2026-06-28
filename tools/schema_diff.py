"""Raw schema diff primitives for source-to-target catalog comparisons."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tools.schema_introspection import (
    ColumnSchema,
    ConstraintSchema,
    DatabaseSchema,
    TableSchema,
)


@dataclass(frozen=True)
class SchemaDelta:
    delta_type: str
    schema: str
    table: str | None = None
    column: str | None = None
    constraint: str | None = None
    source: dict[str, Any] | None = None
    target: dict[str, Any] | None = None

    @property
    def sort_key(self) -> tuple[str, str, str, str, str]:
        return (
            self.schema,
            self.table or "",
            self.column or "",
            self.constraint or "",
            self.delta_type,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "delta_type": self.delta_type,
            "schema": self.schema,
            "table": self.table,
            "column": self.column,
            "constraint": self.constraint,
            "source": self.source,
            "target": self.target,
        }
        return {key: value for key, value in payload.items() if value is not None}


def diff_database_schemas(
    source_schema: DatabaseSchema,
    target_schema: DatabaseSchema,
) -> tuple[SchemaDelta, ...]:
    """Return raw source-to-target schema deltas without assigning risk policy."""

    source_tables = source_schema.table_map
    target_tables = target_schema.table_map
    deltas: list[SchemaDelta] = []

    for schema, table in sorted(source_tables.keys() - target_tables.keys()):
        deltas.append(
            SchemaDelta(
                delta_type="missing_table",
                schema=schema,
                table=table,
                source=source_tables[(schema, table)].to_dict(),
            )
        )

    for schema, table in sorted(target_tables.keys() - source_tables.keys()):
        deltas.append(
            SchemaDelta(
                delta_type="extra_table",
                schema=schema,
                table=table,
                target=target_tables[(schema, table)].to_dict(),
            )
        )

    for key in sorted(source_tables.keys() & target_tables.keys()):
        deltas.extend(_diff_table(source_tables[key], target_tables[key]))

    return tuple(sorted(deltas, key=lambda delta: delta.sort_key))


def _diff_table(source_table: TableSchema, target_table: TableSchema) -> list[SchemaDelta]:
    return [
        *_diff_columns(source_table, target_table),
        *_diff_constraints(source_table, target_table),
    ]


def _diff_columns(source_table: TableSchema, target_table: TableSchema) -> list[SchemaDelta]:
    source_columns = source_table.column_map
    target_columns = target_table.column_map
    deltas: list[SchemaDelta] = []

    for column_name in sorted(source_columns.keys() - target_columns.keys()):
        deltas.append(
            SchemaDelta(
                delta_type="missing_column",
                schema=source_table.schema,
                table=source_table.name,
                column=column_name,
                source=source_columns[column_name].to_dict(),
            )
        )

    for column_name in sorted(target_columns.keys() - source_columns.keys()):
        deltas.append(
            SchemaDelta(
                delta_type="extra_column",
                schema=source_table.schema,
                table=source_table.name,
                column=column_name,
                target=target_columns[column_name].to_dict(),
            )
        )

    for column_name in sorted(source_columns.keys() & target_columns.keys()):
        source_column = source_columns[column_name]
        target_column = target_columns[column_name]
        if source_column.type_signature != target_column.type_signature:
            deltas.append(
                SchemaDelta(
                    delta_type="changed_column_type",
                    schema=source_table.schema,
                    table=source_table.name,
                    column=column_name,
                    source=_column_type_payload(source_column),
                    target=_column_type_payload(target_column),
                )
            )
        if source_column.nullable != target_column.nullable:
            deltas.append(
                SchemaDelta(
                    delta_type="changed_nullability",
                    schema=source_table.schema,
                    table=source_table.name,
                    column=column_name,
                    source={"nullable": source_column.nullable},
                    target={"nullable": target_column.nullable},
                )
            )

    return deltas


def _diff_constraints(source_table: TableSchema, target_table: TableSchema) -> list[SchemaDelta]:
    source_constraints = source_table.constraint_map
    target_constraints = target_table.constraint_map
    deltas: list[SchemaDelta] = []

    for constraint_name in sorted(source_constraints.keys() - target_constraints.keys()):
        source_constraint = source_constraints[constraint_name]
        deltas.append(
            SchemaDelta(
                delta_type=f"missing_{_constraint_label(source_constraint)}",
                schema=source_table.schema,
                table=source_table.name,
                constraint=constraint_name,
                source=source_constraint.to_dict(),
            )
        )

    for constraint_name in sorted(target_constraints.keys() - source_constraints.keys()):
        target_constraint = target_constraints[constraint_name]
        deltas.append(
            SchemaDelta(
                delta_type=f"extra_{_constraint_label(target_constraint)}",
                schema=source_table.schema,
                table=source_table.name,
                constraint=constraint_name,
                target=target_constraint.to_dict(),
            )
        )

    for constraint_name in sorted(source_constraints.keys() & target_constraints.keys()):
        source_constraint = source_constraints[constraint_name]
        target_constraint = target_constraints[constraint_name]
        if source_constraint.signature != target_constraint.signature:
            deltas.append(
                SchemaDelta(
                    delta_type=f"changed_{_constraint_label(source_constraint)}",
                    schema=source_table.schema,
                    table=source_table.name,
                    constraint=constraint_name,
                    source=source_constraint.to_dict(),
                    target=target_constraint.to_dict(),
                )
            )

    return deltas


def _column_type_payload(column: ColumnSchema) -> dict[str, Any]:
    payload = {
        "data_type": column.data_type,
        "type_signature": column.type_signature,
        "numeric_precision": column.numeric_precision,
        "numeric_scale": column.numeric_scale,
        "character_maximum_length": column.character_maximum_length,
        "datetime_precision": column.datetime_precision,
    }
    return {key: value for key, value in payload.items() if value is not None}


def _constraint_label(constraint: ConstraintSchema) -> str:
    if constraint.constraint_type == "primary_key":
        return "primary_key"
    return f"{constraint.constraint_type}_constraint"
