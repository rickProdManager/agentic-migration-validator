"""Map raw schema deltas to structured findings and follow-up data checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from tools.schema_diff import SchemaDelta


@dataclass(frozen=True)
class SchemaDataCheck:
    check_type: str
    schema: str
    table: str
    column: str | None = None
    constraint: str | None = None
    columns: tuple[str, ...] = ()

    @property
    def evidence_ref(self) -> str:
        subject = self.constraint or self.column or "_"
        return f"schema.data_check.{self.check_type}.{self.schema}.{self.table}.{subject}.v1"

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "check_type": self.check_type,
            "schema": self.schema,
            "table": self.table,
            "column": self.column,
            "constraint": self.constraint,
            "columns": list(self.columns) if self.columns else None,
            "evidence_ref": self.evidence_ref,
        }
        return {key: value for key, value in payload.items() if value is not None}


@dataclass(frozen=True)
class SchemaPolicyResult:
    findings: tuple[dict[str, Any], ...]
    follow_up_checks: tuple[SchemaDataCheck, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "findings": list(self.findings),
            "follow_up_checks": [check.to_dict() for check in self.follow_up_checks],
        }


def map_schema_deltas(
    deltas: Iterable[SchemaDelta],
    *,
    critical_tables: Iterable[str] = (),
) -> SchemaPolicyResult:
    """Route raw deltas by axis first, then by severity."""

    critical_table_set = set(critical_tables)
    findings: list[dict[str, Any]] = []
    follow_up_checks: list[SchemaDataCheck] = []

    for delta in deltas:
        mapped_findings, mapped_checks = _map_delta(delta, critical_table_set)
        findings.extend(mapped_findings)
        follow_up_checks.extend(mapped_checks)

    return SchemaPolicyResult(
        findings=tuple(findings),
        follow_up_checks=tuple(follow_up_checks),
    )


def _map_delta(
    delta: SchemaDelta,
    critical_tables: set[str],
) -> tuple[list[dict[str, Any]], list[SchemaDataCheck]]:
    if delta.delta_type == "missing_table":
        return (
            [
                _finding(
                    delta,
                    finding_type="schema.missing_table",
                    risk_axis="migration_integrity",
                    severity="high",
                    gate_effect=["blocks_cutover", "blocks_ready"],
                    base_points=60,
                    critical_path=_is_critical(delta, critical_tables),
                    summary=f"Target is missing source table {delta.schema}.{delta.table}.",
                )
            ],
            [],
        )

    if delta.delta_type == "extra_table":
        return (
            [
                _finding(
                    delta,
                    finding_type="schema.extra_target_table",
                    risk_axis="compatibility_advisory",
                    severity="low",
                    gate_effect=[],
                    base_points=5,
                    critical_path=False,
                    summary=f"Target has extra table {delta.schema}.{delta.table}.",
                )
            ],
            [],
        )

    if delta.delta_type == "missing_column":
        return (
            [
                _finding(
                    delta,
                    finding_type="schema.missing_column",
                    risk_axis="migration_integrity",
                    severity="high",
                    gate_effect=["blocks_cutover", "blocks_ready"],
                    base_points=55,
                    critical_path=_is_critical(delta, critical_tables),
                    summary=f"Target is missing source column {delta.schema}.{delta.table}.{delta.column}.",
                )
            ],
            [],
        )

    if delta.delta_type == "extra_column":
        return (
            [
                _finding(
                    delta,
                    finding_type="schema.extra_target_column",
                    risk_axis="compatibility_advisory",
                    severity="low",
                    gate_effect=[],
                    base_points=5,
                    critical_path=False,
                    summary=f"Target has extra column {delta.schema}.{delta.table}.{delta.column}.",
                )
            ],
            [],
        )

    if delta.delta_type == "changed_column_type":
        direction = _type_change_direction(delta)
        if direction == "widened":
            return (
                [
                    _finding(
                        delta,
                        finding_type="schema.type_widened",
                        risk_axis="compatibility_advisory",
                        severity="low",
                        gate_effect=[],
                        base_points=5,
                        critical_path=False,
                        summary=_type_change_summary(delta, "widened"),
                    )
                ],
                [],
            )
        return (
            [
                _finding(
                    delta,
                    finding_type="schema.type_narrowed"
                    if direction == "narrowed"
                    else "schema.type_changed",
                    risk_axis="migration_integrity",
                    severity="high" if direction == "narrowed" else "moderate",
                    gate_effect=["blocks_cutover", "blocks_ready"]
                    if direction == "narrowed"
                    else ["blocks_validation_acceptance"],
                    base_points=55 if direction == "narrowed" else 30,
                    critical_path=_is_critical(delta, critical_tables),
                    summary=_type_change_summary(delta, direction),
                )
            ],
            [],
        )

    if delta.delta_type == "changed_nullability":
        source_nullable = bool((delta.source or {}).get("nullable"))
        target_nullable = bool((delta.target or {}).get("nullable"))
        if not source_nullable and target_nullable:
            check = SchemaDataCheck(
                check_type="nulls_in_relaxed_required_column",
                schema=delta.schema,
                table=_required_table(delta),
                column=delta.column,
            )
            return (
                [
                    _finding(
                        delta,
                        finding_type="schema.nullability_relaxed",
                        risk_axis="migration_integrity",
                        severity="low",
                        gate_effect=[],
                        base_points=10,
                        critical_path=_is_critical(delta, critical_tables),
                        summary=(
                            f"Target relaxed NOT NULL on "
                            f"{delta.schema}.{delta.table}.{delta.column}; row data must confirm no NULLs exist."
                        ),
                        evidence_refs=[_evidence_ref(delta), check.evidence_ref],
                    )
                ],
                [check],
            )
        return (
            [
                _finding(
                    delta,
                    finding_type="schema.nullability_restricted",
                    risk_axis="migration_integrity",
                    severity="moderate",
                    gate_effect=["blocks_validation_acceptance"],
                    base_points=30,
                    critical_path=_is_critical(delta, critical_tables),
                    summary=f"Target made {delta.schema}.{delta.table}.{delta.column} more restrictive.",
                )
            ],
            [],
        )

    if delta.delta_type == "missing_unique_constraint":
        columns = tuple((delta.source or {}).get("columns", ()))
        check = SchemaDataCheck(
            check_type="duplicates_after_unique_relaxation",
            schema=delta.schema,
            table=_required_table(delta),
            constraint=delta.constraint,
            columns=columns,
        )
        return (
            [
                _finding(
                    delta,
                    finding_type="schema.unique_constraint_relaxed",
                    risk_axis="migration_integrity",
                    severity="low",
                    gate_effect=[],
                    base_points=10,
                    critical_path=_is_critical(delta, critical_tables),
                    summary=(
                        f"Target dropped unique constraint {delta.constraint}; "
                        "row data must confirm duplicate values were not introduced."
                    ),
                    evidence_refs=[_evidence_ref(delta), check.evidence_ref],
                )
            ],
            [check],
        )

    if delta.delta_type in {"missing_primary_key", "missing_foreign_key_constraint"}:
        finding_type = (
            "schema.missing_primary_key"
            if delta.delta_type == "missing_primary_key"
            else "schema.missing_foreign_key"
        )
        return (
            [
                _finding(
                    delta,
                    finding_type=finding_type,
                    risk_axis="migration_integrity",
                    severity="high",
                    gate_effect=["blocks_cutover", "blocks_ready"],
                    base_points=55,
                    critical_path=_is_critical(delta, critical_tables),
                    summary=f"Target is missing source constraint {delta.constraint}.",
                )
            ],
            [],
        )

    if delta.delta_type.startswith("extra_"):
        return (
            [
                _finding(
                    delta,
                    finding_type="schema.extra_target_constraint",
                    risk_axis="compatibility_advisory",
                    severity="low",
                    gate_effect=[],
                    base_points=5,
                    critical_path=False,
                    summary=f"Target has extra constraint {delta.constraint}.",
                )
            ],
            [],
        )

    return (
        [
            _finding(
                delta,
                finding_type="schema.unclassified_delta",
                risk_axis="migration_integrity",
                severity="moderate",
                gate_effect=["blocks_validation_acceptance"],
                base_points=25,
                critical_path=_is_critical(delta, critical_tables),
                summary=f"Target schema changed: {delta.delta_type}.",
            )
        ],
        [],
    )


def _finding(
    delta: SchemaDelta,
    *,
    finding_type: str,
    risk_axis: str,
    severity: str,
    gate_effect: list[str],
    base_points: int,
    critical_path: bool,
    summary: str,
    evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "record_type": "detector_finding",
        "risk_axis": risk_axis,
        "finding_key": _finding_key(delta, finding_type),
        "finding_type": finding_type,
        "detector": "schema_diff",
        "severity": severity,
        "status": "unresolved",
        "gate_effect": gate_effect,
        "scope": {
            "schema": delta.schema,
            "table": delta.table,
            "column": delta.column,
            "constraint": delta.constraint,
            "business_key": None,
        },
        "blast_radius": {
            "affected_tables": 1 if delta.table else None,
            "affected_rows": None,
            "source_rows": None,
            "affected_row_percent": None,
            "critical_path": critical_path,
        },
        "base_points": base_points,
        "risk_points": base_points,
        "evidence_refs": evidence_refs or [_evidence_ref(delta)],
        "summary": summary,
    }


def _type_change_direction(delta: SchemaDelta) -> str:
    source = delta.source or {}
    target = delta.target or {}
    source_type = str(source.get("data_type", "")).lower()
    target_type = str(target.get("data_type", "")).lower()

    if source_type in {"numeric", "decimal"} and target_type in {"numeric", "decimal"}:
        source_integer_digits = _integer_digits(source)
        target_integer_digits = _integer_digits(target)
        source_scale = _optional_int(source.get("numeric_scale"))
        target_scale = _optional_int(target.get("numeric_scale"))
        if (
            source_integer_digits is not None
            and target_integer_digits is not None
            and source_scale is not None
            and target_scale is not None
        ):
            if target_integer_digits >= source_integer_digits and target_scale >= source_scale:
                return "widened"
            if target_integer_digits < source_integer_digits or target_scale < source_scale:
                return "narrowed"

    if source_type in {"character varying", "varchar", "character", "char"} and target_type in {
        "character varying",
        "varchar",
        "character",
        "char",
    }:
        source_length = _optional_int(source.get("character_maximum_length"))
        target_length = _optional_int(target.get("character_maximum_length"))
        if target_length is None and source_length is not None:
            return "widened"
        if source_length is not None and target_length is not None:
            return "widened" if target_length >= source_length else "narrowed"

    integer_rank = {"smallint": 1, "integer": 2, "bigint": 3}
    if source_type in integer_rank and target_type in integer_rank:
        return "widened" if integer_rank[target_type] >= integer_rank[source_type] else "narrowed"

    return "changed"


def _integer_digits(payload: dict[str, Any]) -> int | None:
    precision = _optional_int(payload.get("numeric_precision"))
    scale = _optional_int(payload.get("numeric_scale"))
    if precision is None or scale is None:
        return None
    return precision - scale


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _finding_key(delta: SchemaDelta, finding_type: str) -> str:
    subject = delta.constraint or delta.column or "*"
    if delta.table:
        return f"{finding_type}:{delta.schema}.{delta.table}:{subject}"
    return f"{finding_type}:{delta.schema}:*:{subject}"


def _evidence_ref(delta: SchemaDelta) -> str:
    subject = delta.constraint or delta.column or "*"
    table = delta.table or "*"
    return f"schema.diff.{delta.schema}.{table}.{subject}.v1"


def _is_critical(delta: SchemaDelta, critical_tables: set[str]) -> bool:
    return bool(delta.table and delta.table in critical_tables)


def _required_table(delta: SchemaDelta) -> str:
    if delta.table is None:
        raise ValueError(f"Delta requires a table: {delta!r}")
    return delta.table


def _type_change_summary(delta: SchemaDelta, direction: str) -> str:
    source_type = (delta.source or {}).get("type_signature", "unknown")
    target_type = (delta.target or {}).get("type_signature", "unknown")
    return (
        f"Target {direction} type for {delta.schema}.{delta.table}.{delta.column}: "
        f"{source_type} -> {target_type}."
    )
