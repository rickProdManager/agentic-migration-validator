"""Checksum validation detector over canonical table digests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from tools.checksum import CANONICALIZATION_VERSION, ColumnSpec, table_digest


CHECKSUM_MISMATCH_BASE_POINTS = 35


@dataclass(frozen=True)
class TableChecksumEvidence:
    schema: str
    table: str
    source_digest: str
    target_digest: str
    source_row_count: int
    target_row_count: int
    evidence_ref: str
    canonicalization_version: str = CANONICALIZATION_VERSION

    @property
    def matched(self) -> bool:
        return self.source_digest == self.target_digest

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "table": self.table,
            "source_digest": self.source_digest,
            "target_digest": self.target_digest,
            "source_row_count": self.source_row_count,
            "target_row_count": self.target_row_count,
            "matched": self.matched,
            "evidence_ref": self.evidence_ref,
            "canonicalization_version": self.canonicalization_version,
        }


def compare_table_checksum(
    *,
    schema: str,
    table: str,
    columns: Iterable[ColumnSpec],
    source_rows: Iterable[Mapping[str, Any]],
    target_rows: Iterable[Mapping[str, Any]],
    critical_path: bool = False,
) -> tuple[TableChecksumEvidence, dict[str, Any] | None]:
    """Compare source and target table digests and emit a finding on mismatch."""

    source_row_tuple = tuple(source_rows)
    target_row_tuple = tuple(target_rows)
    column_tuple = tuple(columns)
    evidence_ref = f"validation.checksum.{schema}.{table}.v1"
    evidence = TableChecksumEvidence(
        schema=schema,
        table=table,
        source_digest=table_digest(source_row_tuple, column_tuple),
        target_digest=table_digest(target_row_tuple, column_tuple),
        source_row_count=len(source_row_tuple),
        target_row_count=len(target_row_tuple),
        evidence_ref=evidence_ref,
    )

    if evidence.matched:
        return evidence, None

    return evidence, _checksum_mismatch_finding(
        schema=schema,
        table=table,
        evidence=evidence,
        critical_path=critical_path,
    )


def _checksum_mismatch_finding(
    *,
    schema: str,
    table: str,
    evidence: TableChecksumEvidence,
    critical_path: bool,
) -> dict[str, Any]:
    return {
        "record_type": "detector_finding",
        "risk_axis": "migration_integrity",
        "finding_key": f"validation.checksum_mismatch:{schema}.{table}:*",
        "finding_type": "validation.checksum_mismatch",
        "detector": "canonical_checksum",
        "severity": "high",
        "status": "unresolved",
        "gate_effect": ["blocks_cutover", "blocks_ready"],
        "scope": {
            "schema": schema,
            "table": table,
            "column": None,
            "constraint": None,
            "business_key": None,
        },
        "blast_radius": {
            "affected_tables": 1,
            "affected_rows": None,
            "source_rows": evidence.source_row_count,
            "affected_row_percent": None,
            "critical_path": critical_path,
        },
        "base_points": CHECKSUM_MISMATCH_BASE_POINTS,
        "risk_points": CHECKSUM_MISMATCH_BASE_POINTS,
        "evidence_refs": [evidence.evidence_ref],
        "summary": f"Canonical checksum mismatch for {schema}.{table}.",
    }
