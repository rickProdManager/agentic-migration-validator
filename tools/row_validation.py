"""Row presence and lag-aware freshness validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping


MISSING_ROWS_BASE_POINTS = 30


@dataclass(frozen=True)
class TableRowPresenceEvidence:
    schema: str
    table: str
    primary_key_columns: tuple[str, ...]
    source_row_count: int
    target_row_count: int
    missing_source_row_count: int
    explained_lag_row_count: int
    unexplained_missing_row_count: int
    evidence_ref: str
    freshness_column: str | None = None
    source_cutoff: str | None = None

    @property
    def matched(self) -> bool:
        return self.missing_source_row_count == 0

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema": self.schema,
            "table": self.table,
            "primary_key_columns": list(self.primary_key_columns),
            "source_row_count": self.source_row_count,
            "target_row_count": self.target_row_count,
            "missing_source_row_count": self.missing_source_row_count,
            "explained_lag_row_count": self.explained_lag_row_count,
            "unexplained_missing_row_count": self.unexplained_missing_row_count,
            "matched": self.matched,
            "evidence_ref": self.evidence_ref,
            "freshness_column": self.freshness_column,
            "source_cutoff": self.source_cutoff,
        }
        return {key: value for key, value in payload.items() if value is not None}


def compare_table_row_presence(
    *,
    schema: str,
    table: str,
    primary_key_columns: Iterable[str],
    source_rows: Iterable[Mapping[str, Any]],
    target_rows: Iterable[Mapping[str, Any]],
    lag_policy: Mapping[str, Any] | None = None,
    critical_path: bool = False,
) -> tuple[TableRowPresenceEvidence, dict[str, Any] | None]:
    """Detect source rows missing from target, distinguishing explained lag."""

    primary_key_tuple = tuple(primary_key_columns)
    source_row_tuple = tuple(source_rows)
    target_row_tuple = tuple(target_rows)
    missing_source_rows = _missing_source_rows(
        primary_key_columns=primary_key_tuple,
        source_rows=source_row_tuple,
        target_rows=target_row_tuple,
    )
    freshness_column = _lag_policy_value(lag_policy, "freshness_column")
    source_cutoff = _lag_policy_value(lag_policy, "source_cutoff")
    explained_rows, unexplained_rows = _split_lag_explained_rows(
        missing_source_rows,
        freshness_column=freshness_column,
        source_cutoff=source_cutoff,
    )
    evidence_ref = f"validation.row_presence.{schema}.{table}.v1"
    evidence = TableRowPresenceEvidence(
        schema=schema,
        table=table,
        primary_key_columns=primary_key_tuple,
        source_row_count=len(source_row_tuple),
        target_row_count=len(target_row_tuple),
        missing_source_row_count=len(missing_source_rows),
        explained_lag_row_count=len(explained_rows),
        unexplained_missing_row_count=len(unexplained_rows),
        evidence_ref=evidence_ref,
        freshness_column=freshness_column,
        source_cutoff=source_cutoff,
    )

    if not missing_source_rows:
        return evidence, None
    if unexplained_rows:
        return evidence, _missing_rows_finding(
            schema=schema,
            table=table,
            evidence=evidence,
            critical_path=critical_path,
        )
    return evidence, _replication_lag_finding(
        schema=schema,
        table=table,
        evidence=evidence,
        critical_path=critical_path,
    )


def _missing_source_rows(
    *,
    primary_key_columns: tuple[str, ...],
    source_rows: tuple[Mapping[str, Any], ...],
    target_rows: tuple[Mapping[str, Any], ...],
) -> tuple[Mapping[str, Any], ...]:
    if not primary_key_columns:
        return ()

    target_keys = {
        _row_key(row, primary_key_columns)
        for row in target_rows
    }
    return tuple(
        row for row in source_rows
        if _row_key(row, primary_key_columns) not in target_keys
    )


def _row_key(row: Mapping[str, Any], primary_key_columns: tuple[str, ...]) -> tuple[Any, ...]:
    return tuple(row.get(column) for column in primary_key_columns)


def _split_lag_explained_rows(
    rows: tuple[Mapping[str, Any], ...],
    *,
    freshness_column: str | None,
    source_cutoff: str | None,
) -> tuple[tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...]]:
    if not freshness_column or not source_cutoff:
        return (), rows

    cutoff = _parse_timestamp(source_cutoff)
    explained = []
    unexplained = []
    for row in rows:
        value = row.get(freshness_column)
        if value is not None and _parse_timestamp(value) > cutoff:
            explained.append(row)
        else:
            unexplained.append(row)
    return tuple(explained), tuple(unexplained)


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _lag_policy_value(lag_policy: Mapping[str, Any] | None, key: str) -> str | None:
    if not lag_policy:
        return None
    value = lag_policy.get(key)
    return str(value) if value else None


def _missing_rows_finding(
    *,
    schema: str,
    table: str,
    evidence: TableRowPresenceEvidence,
    critical_path: bool,
) -> dict[str, Any]:
    return {
        "record_type": "detector_finding",
        "risk_axis": "migration_integrity",
        "finding_key": f"validation.missing_rows:{schema}.{table}:*",
        "finding_type": "validation.missing_rows",
        "detector": "row_presence",
        "severity": "high",
        "status": "unresolved",
        "gate_effect": ["blocks_cutover", "blocks_ready"],
        "scope": _scope(schema, table),
        "blast_radius": _blast_radius(
            evidence=evidence,
            affected_rows=evidence.unexplained_missing_row_count,
            critical_path=critical_path,
        ),
        "base_points": MISSING_ROWS_BASE_POINTS,
        "risk_points": MISSING_ROWS_BASE_POINTS,
        "evidence_refs": [evidence.evidence_ref],
        "summary": (
            f"Target is missing {evidence.unexplained_missing_row_count} unexplained "
            f"source row(s) from {schema}.{table}."
        ),
    }


def _replication_lag_finding(
    *,
    schema: str,
    table: str,
    evidence: TableRowPresenceEvidence,
    critical_path: bool,
) -> dict[str, Any]:
    return {
        "record_type": "detector_finding",
        "risk_axis": "migration_integrity",
        "finding_key": f"validation.replication_lag:{schema}.{table}:*",
        "finding_type": "validation.replication_lag",
        "detector": "lag_aware_row_freshness",
        "severity": "info",
        "status": "unresolved",
        "gate_effect": [],
        "scope": _scope(schema, table),
        "blast_radius": _blast_radius(
            evidence=evidence,
            affected_rows=evidence.explained_lag_row_count,
            critical_path=critical_path,
        ),
        "base_points": 0,
        "risk_points": 0,
        "evidence_refs": [evidence.evidence_ref],
        "known_cutoff": evidence.source_cutoff,
        "summary": (
            f"Target trails source by {evidence.explained_lag_row_count} row(s) in "
            f"{schema}.{table} after cutoff {evidence.source_cutoff}."
        ),
    }


def _scope(schema: str, table: str) -> dict[str, str | None]:
    return {
        "schema": schema,
        "table": table,
        "column": None,
        "constraint": None,
        "business_key": None,
    }


def _blast_radius(
    *,
    evidence: TableRowPresenceEvidence,
    affected_rows: int,
    critical_path: bool,
) -> dict[str, Any]:
    return {
        "affected_tables": 1,
        "affected_rows": affected_rows,
        "source_rows": evidence.source_row_count,
        "affected_row_percent": _affected_row_percent(
            affected_rows,
            evidence.source_row_count,
        ),
        "critical_path": critical_path,
    }


def _affected_row_percent(affected_rows: int, source_rows: int) -> float:
    if source_rows == 0:
        return 0.0
    return round((affected_rows / source_rows) * 100, 2)
