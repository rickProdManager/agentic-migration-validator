#!/usr/bin/env python3
"""Run raw schema diff introspection against the Docker fixture databases."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.schema_diff import diff_database_schemas
from tools.schema_introspection import database_schema_from_catalog_rows


def main(argv: list[str]) -> int:
    scenario_id = argv[1] if len(argv) > 1 else "clean_migration"
    result = diff_schema_for_scenario(scenario_id)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def diff_schema_for_scenario(scenario_id: str) -> dict[str, Any]:
    _reset_scenario(scenario_id)
    source_schema = _fetch_database_schema("source-postgres")
    target_schema = _fetch_database_schema("target-postgres")
    deltas = diff_database_schemas(source_schema, target_schema)

    return {
        "scenario_id": scenario_id,
        "model_calls": "disabled",
        "stage": "schema_introspection",
        "detector": "schema_diff_raw",
        "delta_count": len(deltas),
        "deltas": [delta.to_dict() for delta in deltas],
    }


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
