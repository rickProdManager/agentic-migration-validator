"""Detection eval matching over stable structured finding keys."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class EvalResult:
    detected: tuple[dict[str, Any], ...]
    missed: tuple[dict[str, Any], ...]
    false_positives: tuple[dict[str, Any], ...]
    severity_mismatches: tuple[dict[str, Any], ...]
    scope_mismatches: tuple[dict[str, Any], ...]
    axis_mismatches: tuple[dict[str, Any], ...]

    @property
    def passed(self) -> bool:
        return not (
            self.missed
            or self.false_positives
            or self.severity_mismatches
            or self.scope_mismatches
            or self.axis_mismatches
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "detected": list(self.detected),
            "missed": list(self.missed),
            "false_positives": list(self.false_positives),
            "severity_mismatches": list(self.severity_mismatches),
            "scope_mismatches": list(self.scope_mismatches),
            "axis_mismatches": list(self.axis_mismatches),
        }


def evaluate_findings(
    *,
    expected_findings: Iterable[Mapping[str, Any]],
    produced_findings: Iterable[Mapping[str, Any]],
    allowed_extra_findings: Iterable[Mapping[str, Any] | str] = (),
) -> EvalResult:
    """Compare expected and produced detector findings by stable finding key."""

    expected_by_key = _by_finding_key(_detector_findings(expected_findings))
    produced_by_key = _by_finding_key(_detector_findings(produced_findings))
    allowed_extra_keys = _finding_keys(allowed_extra_findings)

    detected = []
    missed = []
    false_positives = []
    severity_mismatches = []
    scope_mismatches = []
    axis_mismatches = []

    for finding_key, expected in expected_by_key.items():
        produced = produced_by_key.get(finding_key)
        if produced is None:
            missed.append(_finding_summary(expected))
            continue

        detected.append({"finding_key": finding_key})
        if produced.get("severity") != expected.get("severity"):
            severity_mismatches.append(
                {
                    "finding_key": finding_key,
                    "expected": expected.get("severity"),
                    "actual": produced.get("severity"),
                }
            )
        if produced.get("scope") != expected.get("scope"):
            scope_mismatches.append(
                {
                    "finding_key": finding_key,
                    "expected": expected.get("scope"),
                    "actual": produced.get("scope"),
                }
            )
        if produced.get("risk_axis") != expected.get("risk_axis"):
            axis_mismatches.append(
                {
                    "finding_key": finding_key,
                    "expected": expected.get("risk_axis"),
                    "actual": produced.get("risk_axis"),
                }
            )

    for finding_key, produced in produced_by_key.items():
        if finding_key not in expected_by_key and finding_key not in allowed_extra_keys:
            false_positives.append(_finding_summary(produced))

    return EvalResult(
        detected=tuple(detected),
        missed=tuple(missed),
        false_positives=tuple(false_positives),
        severity_mismatches=tuple(severity_mismatches),
        scope_mismatches=tuple(scope_mismatches),
        axis_mismatches=tuple(axis_mismatches),
    )


def _detector_findings(findings: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [finding for finding in findings if finding.get("record_type") == "detector_finding"]


def _by_finding_key(findings: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    keyed = {}
    for finding in findings:
        finding_key = finding.get("finding_key")
        if not finding_key:
            raise ValueError("Detector finding is missing finding_key")
        if finding_key in keyed:
            raise ValueError(f"Duplicate finding_key: {finding_key}")
        keyed[finding_key] = finding
    return keyed


def _finding_keys(findings: Iterable[Mapping[str, Any] | str]) -> set[str]:
    keys = set()
    for finding in findings:
        if isinstance(finding, str):
            keys.add(finding)
        else:
            finding_key = finding.get("finding_key")
            if not finding_key:
                raise ValueError("Allowed extra finding is missing finding_key")
            keys.add(finding_key)
    return keys


def _finding_summary(finding: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "finding_key": finding.get("finding_key"),
        "finding_type": finding.get("finding_type"),
        "risk_axis": finding.get("risk_axis"),
        "severity": finding.get("severity"),
        "scope": finding.get("scope"),
    }
