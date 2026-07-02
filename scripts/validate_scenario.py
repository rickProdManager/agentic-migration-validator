#!/usr/bin/env python3
"""Run deterministic checksum validation against the Docker fixture databases."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_ROOT = PROJECT_ROOT / "fixtures" / "scenarios"
VALID_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
sys.path.insert(0, str(PROJECT_ROOT))

from tools.checksum import ColumnSpec
from tools.checksum_validation import compare_table_checksum
from tools.row_validation import compare_table_row_presence


def main(argv: list[str]) -> int:
    scenario_id = argv[1] if len(argv) > 1 else "clean_migration"
    result = validate_scenario(scenario_id)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def validate_scenario(scenario_id: str) -> dict[str, Any]:
    scenario = _load_scenario(scenario_id)
    tables = _list_tables("source-postgres")
    critical_tables = set(scenario.get("critical_tables", []))

    evidence = []
    findings = []

    for table in tables:
        columns = _fetch_columns("source-postgres", "public", table)
        primary_key_columns = _fetch_primary_key_columns("source-postgres", "public", table)
        source_rows = _fetch_rows("source-postgres", "public", table, columns)
        target_rows = _fetch_rows("target-postgres", "public", table, columns)
        row_evidence, row_finding = compare_table_row_presence(
            schema="public",
            table=table,
            primary_key_columns=primary_key_columns,
            source_rows=source_rows,
            target_rows=target_rows,
            lag_policy=_lag_policy_for_table(scenario, "public", table),
            critical_path=table in critical_tables,
        )
        table_evidence, finding = compare_table_checksum(
            schema="public",
            table=table,
            columns=columns,
            source_rows=source_rows,
            target_rows=target_rows,
            critical_path=table in critical_tables,
        )
        evidence.append(row_evidence.to_dict())
        evidence.append(table_evidence.to_dict())
        if row_finding is not None:
            findings.append(row_finding)
        if finding is not None:
            findings.append(finding)

    return {
        "scenario_id": scenario_id,
        "model_calls": "disabled",
        "stage": "validation",
        "detector": "deterministic_validation",
        "evidence": evidence,
        "findings": findings,
    }


def _load_scenario(scenario_id: str) -> dict[str, Any]:
    path = SCENARIOS_ROOT / scenario_id / "scenario.json"
    if not path.exists():
        raise SystemExit(f"Unknown scenario: {scenario_id}")
    return json.loads(path.read_text())


def _list_tables(service: str) -> list[str]:
    sql = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """
    return [line for line in _psql(service, sql).splitlines() if line]


def _fetch_columns(service: str, schema: str, table: str) -> list[ColumnSpec]:
    sql = f"""
        SELECT COALESCE(
          jsonb_agg(
            jsonb_build_object(
              'name', column_name,
              'logical_type', data_type,
              'precision', numeric_precision,
              'scale', numeric_scale
            )
            ORDER BY column_name
          ),
          '[]'::jsonb
        )::text
        FROM information_schema.columns
        WHERE table_schema = {_sql_literal(schema)}
          AND table_name = {_sql_literal(table)};
    """
    raw_columns = json.loads(_psql(service, sql))
    return [
        ColumnSpec(
            name=column["name"],
            logical_type=column["logical_type"],
            precision=column["precision"],
            scale=column["scale"],
        )
        for column in raw_columns
    ]


def _fetch_rows(
    service: str,
    schema: str,
    table: str,
    columns: list[ColumnSpec],
) -> list[dict[str, Any]]:
    order_by = _order_by_expression(service, schema, table, columns)
    qualified_table = f"{_quote_ident(schema)}.{_quote_ident(table)}"
    sql = f"""
        SELECT COALESCE(
          jsonb_agg(to_jsonb(t) ORDER BY {order_by}),
          '[]'::jsonb
        )::text
        FROM (SELECT * FROM {qualified_table}) AS t;
    """
    rows = json.loads(_psql(service, sql), parse_float=Decimal)
    return [_coerce_row(row, columns) for row in rows]


def _fetch_primary_key_columns(service: str, schema: str, table: str) -> list[str]:
    sql = f"""
        SELECT a.attname
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(i.indkey)
        WHERE i.indisprimary
          AND n.nspname = {_sql_literal(schema)}
          AND c.relname = {_sql_literal(table)}
        ORDER BY array_position(i.indkey, a.attnum);
    """
    return [line for line in _psql(service, sql).splitlines() if line]


def _order_by_expression(
    service: str,
    schema: str,
    table: str,
    columns: list[ColumnSpec],
) -> str:
    sql = f"""
        SELECT a.attname
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(i.indkey)
        WHERE i.indisprimary
          AND n.nspname = {_sql_literal(schema)}
          AND c.relname = {_sql_literal(table)}
        ORDER BY array_position(i.indkey, a.attnum);
    """
    primary_key_columns = [line for line in _psql(service, sql).splitlines() if line]
    order_columns = primary_key_columns or [column.name for column in columns]
    return ", ".join(f"t.{_quote_ident(column)}" for column in order_columns)


def _coerce_row(row: dict[str, Any], columns: list[ColumnSpec]) -> dict[str, Any]:
    coerced = {}
    for column in columns:
        value = row.get(column.name)
        if value is None:
            coerced[column.name] = None
            continue

        logical_type = column.logical_type.lower()
        if logical_type in {"numeric", "decimal"}:
            coerced[column.name] = Decimal(str(value))
        elif logical_type in {"timestamp with time zone", "timestamptz"}:
            coerced[column.name] = datetime.fromisoformat(str(value))
        else:
            coerced[column.name] = value
    return coerced


def _lag_policy_for_table(
    scenario: dict[str, Any],
    schema: str,
    table: str,
) -> dict[str, Any] | None:
    policy = scenario.get("allowed_lag")
    if not isinstance(policy, dict):
        return None
    policy_schema = str(policy.get("schema") or "public")
    policy_table = str(policy.get("table") or "")
    if policy_schema != schema or policy_table != table:
        return None
    return policy


def _psql(service: str, sql: str) -> str:
    completed = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            service,
            "psql",
            "-U",
            "validator_admin",
            "-d",
            "migration_validator",
            "-At",
            "-c",
            sql,
        ],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _quote_ident(identifier: str) -> str:
    if not VALID_IDENTIFIER.fullmatch(identifier):
        raise ValueError(f"Unsafe SQL identifier: {identifier!r}")
    return f'"{identifier}"'


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
