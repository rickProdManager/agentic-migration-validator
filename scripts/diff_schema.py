#!/usr/bin/env python3
"""Run raw schema diff introspection against the Docker fixture databases."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_ROOT = PROJECT_ROOT / "fixtures" / "scenarios"
VALID_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
sys.path.insert(0, str(PROJECT_ROOT))

from tools.schema_diff import diff_database_schemas
from tools.schema_introspection import database_schema_from_catalog_rows
from tools.schema_policy import SchemaDataCheck, map_schema_deltas


def main(argv: list[str]) -> int:
    scenario_id = argv[1] if len(argv) > 1 else "clean_migration"
    result = diff_schema_for_scenario(scenario_id)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def diff_schema_for_scenario(scenario_id: str) -> dict[str, Any]:
    scenario = _load_scenario(scenario_id)
    _reset_scenario(scenario_id)
    source_schema = _fetch_database_schema("source-postgres")
    target_schema = _fetch_database_schema("target-postgres")
    deltas = diff_database_schemas(source_schema, target_schema)
    policy_result = map_schema_deltas(
        deltas,
        critical_tables=scenario.get("critical_tables", []),
    )
    data_check_results, data_check_findings = _run_data_checks(
        "target-postgres",
        policy_result.follow_up_checks,
    )
    findings = [*policy_result.findings, *data_check_findings]

    return {
        "scenario_id": scenario_id,
        "model_calls": "disabled",
        "stage": "schema_introspection",
        "detector": "schema_diff",
        "delta_count": len(deltas),
        "deltas": [delta.to_dict() for delta in deltas],
        "follow_up_checks": [check.to_dict() for check in policy_result.follow_up_checks],
        "data_check_results": data_check_results,
        "findings": findings,
    }


def _load_scenario(scenario_id: str) -> dict[str, Any]:
    path = SCENARIOS_ROOT / scenario_id / "scenario.json"
    if not path.exists():
        raise SystemExit(f"Unknown scenario: {scenario_id}")
    return json.loads(path.read_text())


def _fetch_database_schema(service: str):
    return database_schema_from_catalog_rows(
        tables=json.loads(_psql(service, _TABLES_SQL)),
        columns=json.loads(_psql(service, _COLUMNS_SQL)),
        constraints=json.loads(_psql(service, _CONSTRAINTS_SQL)),
    )


def _reset_scenario(scenario_id: str) -> None:
    env = {**os.environ, "QUIET": "1"}
    subprocess.run(
        ["sh", "scripts/reset_databases.sh", scenario_id],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


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


def _run_data_checks(
    service: str,
    checks: tuple[SchemaDataCheck, ...],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    results = []
    findings = []

    for check in checks:
        if check.check_type == "nulls_in_relaxed_required_column":
            result, finding = _run_null_relaxation_check(service, check)
        elif check.check_type == "duplicates_after_unique_relaxation":
            result, finding = _run_duplicate_relaxation_check(service, check)
        else:
            result = {
                **check.to_dict(),
                "passed": None,
                "status": "not_implemented",
            }
            finding = None

        results.append(result)
        if finding is not None:
            findings.append(finding)

    return results, findings


def _run_null_relaxation_check(
    service: str,
    check: SchemaDataCheck,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if check.column is None:
        raise ValueError(f"Null relaxation check requires column: {check!r}")

    sql = f"""
        SELECT COUNT(*)::integer
        FROM {_qualified_table(check.schema, check.table)}
        WHERE {_quote_ident(check.column)} IS NULL;
    """
    null_count = int(_psql(service, sql))
    result = {
        **check.to_dict(),
        "status": "passed" if null_count == 0 else "failed",
        "passed": null_count == 0,
        "null_count": null_count,
    }
    if null_count == 0:
        return result, None

    return result, _data_check_finding(
        check,
        finding_type="validation.nulls_in_previously_required_column",
        finding_key_subject=check.column,
        severity="high",
        base_points=50,
        affected_rows=null_count,
        summary=(
            f"Target contains {null_count} NULL value(s) in previously required column "
            f"{check.schema}.{check.table}.{check.column}."
        ),
    )


def _run_duplicate_relaxation_check(
    service: str,
    check: SchemaDataCheck,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if not check.columns:
        raise ValueError(f"Duplicate relaxation check requires columns: {check!r}")

    grouped_columns = ", ".join(_quote_ident(column) for column in check.columns)
    sql = f"""
        SELECT COUNT(*)::integer
        FROM (
          SELECT {grouped_columns}
          FROM {_qualified_table(check.schema, check.table)}
          GROUP BY {grouped_columns}
          HAVING COUNT(*) > 1
        ) duplicate_groups;
    """
    duplicate_group_count = int(_psql(service, sql))
    result = {
        **check.to_dict(),
        "status": "passed" if duplicate_group_count == 0 else "failed",
        "passed": duplicate_group_count == 0,
        "duplicate_group_count": duplicate_group_count,
    }
    if duplicate_group_count == 0:
        return result, None

    return result, _data_check_finding(
        check,
        finding_type="validation.duplicate_values_after_unique_relaxation",
        finding_key_subject=check.constraint,
        severity="high",
        base_points=50,
        affected_rows=None,
        summary=(
            f"Target contains {duplicate_group_count} duplicate group(s) for relaxed unique "
            f"constraint {check.constraint}."
        ),
    )


def _data_check_finding(
    check: SchemaDataCheck,
    *,
    finding_type: str,
    finding_key_subject: str | None,
    severity: str,
    base_points: int,
    affected_rows: int | None,
    summary: str,
) -> dict[str, Any]:
    return {
        "record_type": "detector_finding",
        "risk_axis": "migration_integrity",
        "finding_key": f"{finding_type}:{check.schema}.{check.table}:{finding_key_subject or '*'}",
        "finding_type": finding_type,
        "detector": "schema_triggered_data_check",
        "severity": severity,
        "status": "unresolved",
        "gate_effect": ["blocks_cutover", "blocks_ready"],
        "scope": {
            "schema": check.schema,
            "table": check.table,
            "column": check.column,
            "constraint": check.constraint,
            "business_key": None,
        },
        "blast_radius": {
            "affected_tables": 1,
            "affected_rows": affected_rows,
            "source_rows": None,
            "affected_row_percent": None,
            "critical_path": None,
        },
        "base_points": base_points,
        "risk_points": base_points,
        "evidence_refs": [check.evidence_ref],
        "summary": summary,
    }


def _qualified_table(schema: str, table: str) -> str:
    return f"{_quote_ident(schema)}.{_quote_ident(table)}"


def _quote_ident(identifier: str) -> str:
    if not VALID_IDENTIFIER.fullmatch(identifier):
        raise ValueError(f"Unsafe SQL identifier: {identifier!r}")
    return f'"{identifier}"'


_TABLES_SQL = """
    SELECT COALESCE(
      jsonb_agg(
        jsonb_build_object(
          'table_schema', table_schema,
          'table_name', table_name
        )
        ORDER BY table_schema, table_name
      ),
      '[]'::jsonb
    )::text
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_type = 'BASE TABLE';
"""


_COLUMNS_SQL = """
    SELECT COALESCE(
      jsonb_agg(
        jsonb_build_object(
          'table_schema', table_schema,
          'table_name', table_name,
          'column_name', column_name,
          'ordinal_position', ordinal_position,
          'data_type', data_type,
          'is_nullable', is_nullable,
          'numeric_precision', numeric_precision,
          'numeric_scale', numeric_scale,
          'character_maximum_length', character_maximum_length,
          'datetime_precision', datetime_precision,
          'column_default', column_default
        )
        ORDER BY table_schema, table_name, ordinal_position
      ),
      '[]'::jsonb
    )::text
    FROM information_schema.columns
    WHERE table_schema = 'public';
"""


_CONSTRAINTS_SQL = """
    WITH catalog_constraints AS (
      SELECT
        n.nspname AS table_schema,
        c.relname AS table_name,
        con.conname AS constraint_name,
        CASE con.contype
          WHEN 'p' THEN 'primary_key'
          WHEN 'u' THEN 'unique'
          WHEN 'f' THEN 'foreign_key'
          WHEN 'c' THEN 'check'
          ELSE con.contype::text
        END AS constraint_type,
        COALESCE(
          ARRAY(
            SELECT a.attname
            FROM unnest(con.conkey) WITH ORDINALITY AS key(attnum, ord)
            JOIN pg_attribute a
              ON a.attrelid = con.conrelid
             AND a.attnum = key.attnum
            ORDER BY key.ord
          ),
          ARRAY[]::text[]
        ) AS columns,
        rn.nspname AS referenced_schema,
        rc.relname AS referenced_table,
        COALESCE(
          ARRAY(
            SELECT a.attname
            FROM unnest(con.confkey) WITH ORDINALITY AS key(attnum, ord)
            JOIN pg_attribute a
              ON a.attrelid = con.confrelid
             AND a.attnum = key.attnum
            ORDER BY key.ord
          ),
          ARRAY[]::text[]
        ) AS referenced_columns,
        pg_get_constraintdef(con.oid, true) AS definition
      FROM pg_constraint con
      JOIN pg_class c ON c.oid = con.conrelid
      JOIN pg_namespace n ON n.oid = c.relnamespace
      LEFT JOIN pg_class rc ON rc.oid = con.confrelid
      LEFT JOIN pg_namespace rn ON rn.oid = rc.relnamespace
      WHERE n.nspname = 'public'
    )
    SELECT COALESCE(
      jsonb_agg(
        jsonb_build_object(
          'table_schema', table_schema,
          'table_name', table_name,
          'constraint_name', constraint_name,
          'constraint_type', constraint_type,
          'columns', columns,
          'referenced_schema', referenced_schema,
          'referenced_table', referenced_table,
          'referenced_columns', referenced_columns,
          'definition', definition
        )
        ORDER BY table_schema, table_name, constraint_type, constraint_name
      ),
      '[]'::jsonb
    )::text
    FROM catalog_constraints;
"""


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
