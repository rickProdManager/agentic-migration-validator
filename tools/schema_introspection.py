"""PostgreSQL schema catalog models for deterministic introspection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


CONSTRAINT_TYPE_BY_CODE = {
    "p": "primary_key",
    "primary key": "primary_key",
    "primary_key": "primary_key",
    "u": "unique",
    "unique": "unique",
    "f": "foreign_key",
    "foreign key": "foreign_key",
    "foreign_key": "foreign_key",
    "c": "check",
    "check": "check",
}


@dataclass(frozen=True)
class ColumnSchema:
    name: str
    data_type: str
    nullable: bool
    ordinal_position: int
    numeric_precision: int | None = None
    numeric_scale: int | None = None
    character_maximum_length: int | None = None
    datetime_precision: int | None = None
    column_default: str | None = None

    @property
    def type_signature(self) -> str:
        data_type = self.data_type.lower()
        if data_type in {"numeric", "decimal"}:
            if self.numeric_precision is not None and self.numeric_scale is not None:
                return f"{data_type}({self.numeric_precision},{self.numeric_scale})"
            if self.numeric_precision is not None:
                return f"{data_type}({self.numeric_precision})"
        if data_type in {"character varying", "varchar", "character", "char"}:
            if self.character_maximum_length is not None:
                return f"{data_type}({self.character_maximum_length})"
        if data_type in {"timestamp with time zone", "timestamp without time zone"}:
            if self.datetime_precision is not None:
                return f"{data_type}({self.datetime_precision})"
        return data_type

    def to_dict(self) -> dict[str, Any]:
        return _without_none(
            {
                "name": self.name,
                "data_type": self.data_type,
                "type_signature": self.type_signature,
                "nullable": self.nullable,
                "ordinal_position": self.ordinal_position,
                "numeric_precision": self.numeric_precision,
                "numeric_scale": self.numeric_scale,
                "character_maximum_length": self.character_maximum_length,
                "datetime_precision": self.datetime_precision,
                "column_default": self.column_default,
            }
        )


@dataclass(frozen=True)
class ConstraintSchema:
    name: str
    constraint_type: str
    columns: tuple[str, ...]
    definition: str | None = None
    referenced_schema: str | None = None
    referenced_table: str | None = None
    referenced_columns: tuple[str, ...] = ()

    @property
    def signature(self) -> dict[str, Any]:
        return _without_none(
            {
                "constraint_type": self.constraint_type,
                "columns": list(self.columns),
                "referenced_schema": self.referenced_schema,
                "referenced_table": self.referenced_table,
                "referenced_columns": list(self.referenced_columns)
                if self.referenced_columns
                else None,
                "definition": self.definition,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            **self.signature,
        }


@dataclass(frozen=True)
class TableSchema:
    schema: str
    name: str
    columns: tuple[ColumnSchema, ...] = ()
    constraints: tuple[ConstraintSchema, ...] = ()

    @property
    def qualified_name(self) -> str:
        return f"{self.schema}.{self.name}"

    @property
    def column_map(self) -> dict[str, ColumnSchema]:
        return {column.name: column for column in self.columns}

    @property
    def constraint_map(self) -> dict[str, ConstraintSchema]:
        return {constraint.name: constraint for constraint in self.constraints}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "name": self.name,
            "columns": [column.to_dict() for column in self.columns],
            "constraints": [constraint.to_dict() for constraint in self.constraints],
        }


@dataclass(frozen=True)
class DatabaseSchema:
    tables: tuple[TableSchema, ...]

    @property
    def table_map(self) -> dict[tuple[str, str], TableSchema]:
        return {(table.schema, table.name): table for table in self.tables}

    def to_dict(self) -> dict[str, Any]:
        return {"tables": [table.to_dict() for table in self.tables]}


def database_schema_from_catalog_rows(
    *,
    tables: Iterable[Mapping[str, Any]],
    columns: Iterable[Mapping[str, Any]],
    constraints: Iterable[Mapping[str, Any]] = (),
) -> DatabaseSchema:
    """Build a stable schema model from PostgreSQL catalog query rows."""

    table_keys = {_table_key(row) for row in tables}
    columns_by_table: dict[tuple[str, str], list[ColumnSchema]] = {}
    constraints_by_table: dict[tuple[str, str], list[ConstraintSchema]] = {}

    for row in columns:
        key = _table_key(row)
        table_keys.add(key)
        columns_by_table.setdefault(key, []).append(_column_from_catalog_row(row))

    for row in constraints:
        key = _table_key(row)
        table_keys.add(key)
        constraints_by_table.setdefault(key, []).append(_constraint_from_catalog_row(row))

    table_models = []
    for schema, table in sorted(table_keys):
        table_models.append(
            TableSchema(
                schema=schema,
                name=table,
                columns=tuple(
                    sorted(
                        columns_by_table.get((schema, table), ()),
                        key=lambda column: (column.ordinal_position, column.name),
                    )
                ),
                constraints=tuple(
                    sorted(
                        constraints_by_table.get((schema, table), ()),
                        key=lambda constraint: (constraint.constraint_type, constraint.name),
                    )
                ),
            )
        )

    return DatabaseSchema(tables=tuple(table_models))


def _column_from_catalog_row(row: Mapping[str, Any]) -> ColumnSchema:
    return ColumnSchema(
        name=str(row.get("column_name") or row.get("name")),
        data_type=str(row["data_type"]),
        nullable=_nullable(row.get("is_nullable", row.get("nullable"))),
        ordinal_position=int(row.get("ordinal_position", 0)),
        numeric_precision=_optional_int(row.get("numeric_precision")),
        numeric_scale=_optional_int(row.get("numeric_scale")),
        character_maximum_length=_optional_int(row.get("character_maximum_length")),
        datetime_precision=_optional_int(row.get("datetime_precision")),
        column_default=_optional_str(row.get("column_default")),
    )


def _constraint_from_catalog_row(row: Mapping[str, Any]) -> ConstraintSchema:
    return ConstraintSchema(
        name=str(row.get("constraint_name") or row.get("name")),
        constraint_type=_normalize_constraint_type(row["constraint_type"]),
        columns=_tuple_of_strings(row.get("columns", ())),
        definition=_optional_str(row.get("definition")),
        referenced_schema=_optional_str(row.get("referenced_schema")),
        referenced_table=_optional_str(row.get("referenced_table")),
        referenced_columns=_tuple_of_strings(row.get("referenced_columns", ())),
    )


def _table_key(row: Mapping[str, Any]) -> tuple[str, str]:
    schema = row.get("table_schema") or row.get("schema")
    table = row.get("table_name") or row.get("table")
    if schema is None or table is None:
        raise ValueError(f"Catalog row is missing table identity: {row!r}")
    return str(schema), str(table)


def _normalize_constraint_type(value: Any) -> str:
    key = str(value).strip().lower()
    try:
        return CONSTRAINT_TYPE_BY_CODE[key]
    except KeyError as exc:
        raise ValueError(f"Unsupported constraint type: {value!r}") from exc


def _nullable(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"yes", "true", "1"}


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _tuple_of_strings(values: Any) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


def _without_none(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}
