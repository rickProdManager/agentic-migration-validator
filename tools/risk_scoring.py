"""Deterministic risk scoring for migration readiness findings."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable


RISK_AXES = ("migration_integrity", "compatibility_advisory", "process_control")
CUTOVER_READY_RISK_AXES = ("migration_integrity", "process_control")
BLOCKING_GATE_EFFECTS = frozenset({"blocks_cutover", "blocks_ready"})

SEVERITY_FLOORS = {
    "info": 0,
    "low": 0,
    "moderate": 25,
    "high": 50,
    "critical": 75,
}

RUBRIC = {
    "validation.checksum_mismatch": {
        "record_type": "detector_finding",
        "risk_axis": "migration_integrity",
        "severity": "high",
        "base_points": 35,
    },
    "validation.broken_referential_integrity": {
        "record_type": "detector_finding",
        "risk_axis": "migration_integrity",
        "severity": "high",
        "base_points": 35,
    },
    "validation.missing_rows": {
        "record_type": "detector_finding",
        "risk_axis": "migration_integrity",
        "severity": "high",
        "base_points": 30,
    },
    "schema.missing_primary_key": {
        "record_type": "detector_finding",
        "risk_axis": "migration_integrity",
        "severity": "high",
        "base_points": 25,
    },
    "schema.missing_constraint": {
        "record_type": "detector_finding",
        "risk_axis": "migration_integrity",
        "severity": "moderate",
        "base_points": 15,
    },
    "schema.precision_sensitive_type_change": {
        "record_type": "detector_finding",
        "risk_axis": "migration_integrity",
        "severity": "moderate",
        "base_points": 15,
    },
    "validation.null_distribution_mismatch": {
        "record_type": "detector_finding",
        "risk_axis": "migration_integrity",
        "severity": "moderate",
        "base_points": 12,
    },
    "validation.duplicate_business_key": {
        "record_type": "detector_finding",
        "risk_axis": "migration_integrity",
        "severity": "high",
        "base_points": 20,
    },
    "validation.replication_lag": {
        "record_type": "detector_finding",
        "risk_axis": "migration_integrity",
        "severity": "info",
        "base_points": 0,
    },
    "compatibility.unsupported_feature_critical_path": {
        "record_type": "detector_finding",
        "risk_axis": "compatibility_advisory",
        "severity": "moderate",
        "base_points": 20,
    },
    "compatibility.unsupported_feature_outside_critical_path": {
        "record_type": "detector_finding",
        "risk_axis": "compatibility_advisory",
        "severity": "low",
        "base_points": 8,
    },
    "compatibility.warehouse_precision_or_timestamp_risk": {
        "record_type": "detector_finding",
        "risk_axis": "compatibility_advisory",
        "severity": "low",
        "base_points": 8,
    },
    "gate.required_approval_missing": {
        "record_type": "gate_finding",
        "risk_axis": "process_control",
        "severity": "moderate",
        "base_points": 10,
    },
    "runbook.rollback_criteria_missing": {
        "record_type": "gate_finding",
        "risk_axis": "process_control",
        "severity": "high",
        "base_points": 20,
    },
    "artifact.unresolved_evidence_reference": {
        "record_type": "gate_finding",
        "risk_axis": "process_control",
        "severity": "high",
        "base_points": 25,
    },
    "reviewer.qualitative_critique": {
        "record_type": "gate_finding",
        "risk_axis": "process_control",
        "severity": "low",
        "base_points": 0,
    },
    "risk.derived.compounding_high_validation_failures": {
        "record_type": "derived_risk_factor",
        "risk_axis": "migration_integrity",
        "severity": "critical",
        "base_points": 0,
    },
}


class RiskScoringError(ValueError):
    """Raised when a finding violates risk scoring invariants."""


@dataclass(frozen=True)
class Finding:
    record_type: str
    risk_axis: str
    finding_type: str
    severity: str | None = None
    base_points: int | None = None
    blast_radius_multiplier: float = 1.0
    instance_bonus: int = 0
    gate_effect: tuple[str, ...] = ()
    status: str = "unresolved"


@dataclass(frozen=True)
class ScoredFinding(Finding):
    risk_points: int = 0
    axis_score_floor: int = 0
    per_finding_cap: int = 0


@dataclass(frozen=True)
class AxisScore:
    score: int
    band: str
    raw_score: int
    floor: int


@dataclass(frozen=True)
class RiskScoreResult:
    axes: dict[str, AxisScore]
    findings: tuple[ScoredFinding, ...]
    cutover_ready_risk_axes: tuple[str, ...] = CUTOVER_READY_RISK_AXES


def round_half_up(value: float | int | Decimal) -> int:
    """Round halves away from zero for positive risk scores."""

    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def band_for_score(score: int) -> str:
    if score < 0 or score > 100:
        raise RiskScoringError(f"Score must be between 0 and 100, got {score}")
    if score <= 24:
        return "low"
    if score <= 49:
        return "moderate"
    if score <= 74:
        return "high"
    return "critical"


def score_finding(finding: Finding) -> ScoredFinding:
    normalized = _normalize_finding(finding)
    _validate_finding(normalized)

    severity = _escalated_severity(normalized)
    base_points = normalized.base_points or 0
    cap = base_points * 2
    uncapped = (
        Decimal(str(base_points)) * Decimal(str(normalized.blast_radius_multiplier))
        + Decimal(str(normalized.instance_bonus))
    )
    risk_points = round_half_up(min(uncapped, Decimal(str(cap))))
    floor = SEVERITY_FLOORS[severity]

    return ScoredFinding(
        **{
            **normalized.__dict__,
            "severity": severity,
            "base_points": base_points,
            "risk_points": risk_points,
            "axis_score_floor": floor,
            "per_finding_cap": cap,
        }
    )


def score_risk_axes(findings: Iterable[Finding]) -> RiskScoreResult:
    scored_findings = tuple(score_finding(finding) for finding in findings)
    axes: dict[str, AxisScore] = {}

    for axis in RISK_AXES:
        axis_findings = [
            finding
            for finding in scored_findings
            if finding.risk_axis == axis and finding.status == "unresolved"
        ]
        raw_score = sum(finding.risk_points for finding in axis_findings)
        floor = max((finding.axis_score_floor for finding in axis_findings), default=0)
        score = round_half_up(max(raw_score, floor))
        score = max(0, min(score, 100))
        axes[axis] = AxisScore(
            score=score,
            band=band_for_score(score),
            raw_score=raw_score,
            floor=floor,
        )

    return RiskScoreResult(axes=axes, findings=scored_findings)


def _normalize_finding(finding: Finding) -> Finding:
    rubric = RUBRIC.get(finding.finding_type)
    if rubric is None:
        if finding.base_points is None or finding.severity is None:
            raise RiskScoringError(
                f"Finding {finding.finding_type!r} is not in the rubric and lacks explicit scoring fields"
            )
        return finding

    return replace(
        finding,
        record_type=finding.record_type or rubric["record_type"],
        risk_axis=finding.risk_axis or rubric["risk_axis"],
        severity=finding.severity or rubric["severity"],
        base_points=finding.base_points if finding.base_points is not None else rubric["base_points"],
    )


def _validate_finding(finding: Finding) -> None:
    if finding.record_type not in {"detector_finding", "gate_finding", "derived_risk_factor"}:
        raise RiskScoringError(f"Unknown record_type {finding.record_type!r}")
    if finding.risk_axis not in RISK_AXES:
        raise RiskScoringError(f"Unknown risk_axis {finding.risk_axis!r}")
    if finding.severity not in SEVERITY_FLOORS:
        raise RiskScoringError(f"Unknown severity {finding.severity!r}")
    if finding.blast_radius_multiplier <= 0:
        raise RiskScoringError("blast_radius_multiplier must be positive")
    if finding.instance_bonus < 0:
        raise RiskScoringError("instance_bonus must be non-negative")
    if finding.risk_axis == "compatibility_advisory" and BLOCKING_GATE_EFFECTS.intersection(
        finding.gate_effect
    ):
        raise RiskScoringError(
            "compatibility_advisory findings cannot carry readiness-blocking gate effects"
        )


def _escalated_severity(finding: Finding) -> str:
    if (
        finding.risk_axis == "migration_integrity"
        and finding.record_type == "detector_finding"
        and finding.severity == "high"
        and finding.blast_radius_multiplier >= 2.0
    ):
        return "critical"
    return finding.severity or "info"
