"""Deterministic gate checks over structured findings and workflow state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


CUTOVER_READY_AXES = frozenset({"migration_integrity", "process_control"})
NON_BLOCKING_STATUSES = frozenset({"resolved", "accepted_risk", "not_applicable"})

GATE_EFFECT_BY_GATE = {
    "can_generate_final_plan": "blocks_plan",
    "can_accept_validation": "blocks_validation_acceptance",
    "can_recommend_cutover": "blocks_cutover",
    "can_recommend_rollback": "blocks_rollback",
    "can_mark_ready": "blocks_ready",
}

REQUIRED_APPROVAL_BY_GATE = {
    "can_generate_final_plan": "final_planning",
    "can_accept_validation": "validation_acceptance",
    "can_recommend_cutover": "cutover_recommendation",
    "can_recommend_rollback": "rollback_recommendation",
    "can_mark_ready": "ready",
}


@dataclass(frozen=True)
class GateContext:
    validation_completed: bool = False
    validation_accepted: bool = False
    discovery_artifacts_exist: bool = False
    compatibility_findings_produced: bool = False
    rollback_criteria_exist: bool = False
    blocked_validation_evidence_exists: bool = False
    final_runbook_published: bool = False
    approvals: tuple[str, ...] = ()
    required_evidence_refs: tuple[str, ...] = ()
    resolved_evidence_refs: tuple[str, ...] = ()
    checked_at: str | None = None


@dataclass(frozen=True)
class GateResult:
    gate: str
    allowed: bool
    blocking_findings: tuple[str, ...] = ()
    missing_approvals: tuple[str, ...] = ()
    unresolved_evidence_refs: tuple[str, ...] = ()
    unmet_prerequisites: tuple[str, ...] = ()
    checked_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "gate": self.gate,
            "allowed": self.allowed,
            "blocking_findings": list(self.blocking_findings),
            "missing_approvals": list(self.missing_approvals),
            "unresolved_evidence_refs": list(self.unresolved_evidence_refs),
            "unmet_prerequisites": list(self.unmet_prerequisites),
            "checked_at": self.checked_at,
        }
        return {key: value for key, value in payload.items() if value is not None}


def evaluate_gate(
    gate: str,
    findings: Iterable[Mapping[str, Any]],
    context: GateContext | None = None,
) -> GateResult:
    """Evaluate one deterministic workflow gate."""

    if gate not in GATE_EFFECT_BY_GATE:
        raise ValueError(f"Unknown gate: {gate}")

    gate_context = context or GateContext()
    blocking_findings = _blocking_finding_keys(gate, findings)
    missing_approvals = _missing_approvals(gate, gate_context)
    unresolved_evidence_refs = _unresolved_evidence_refs(gate_context)
    unmet_prerequisites = _unmet_prerequisites(gate, gate_context)
    allowed = not (
        blocking_findings
        or missing_approvals
        or unresolved_evidence_refs
        or unmet_prerequisites
    )

    return GateResult(
        gate=gate,
        allowed=allowed,
        blocking_findings=blocking_findings,
        missing_approvals=missing_approvals,
        unresolved_evidence_refs=unresolved_evidence_refs,
        unmet_prerequisites=unmet_prerequisites,
        checked_at=gate_context.checked_at,
    )


def evaluate_cutover_readiness(
    findings: Iterable[Mapping[str, Any]],
    context: GateContext | None = None,
) -> dict[str, dict[str, Any]]:
    """Return the two PostgreSQL MVP readiness gates used in scenario evals."""

    gate_context = context or GateContext()
    return {
        gate: evaluate_gate(gate, findings, gate_context).to_dict()
        for gate in ("can_recommend_cutover", "can_mark_ready")
    }


def _blocking_finding_keys(
    gate: str,
    findings: Iterable[Mapping[str, Any]],
) -> tuple[str, ...]:
    gate_effect = GATE_EFFECT_BY_GATE[gate]
    blocking = []

    for finding in findings:
        if _is_resolved(finding):
            continue
        if _blocks_gate(finding, gate, gate_effect):
            finding_key = finding.get("finding_key")
            if finding_key:
                blocking.append(str(finding_key))

    return tuple(sorted(set(blocking)))


def _blocks_gate(finding: Mapping[str, Any], gate: str, gate_effect: str) -> bool:
    if gate in {"can_recommend_cutover", "can_mark_ready"}:
        if finding.get("risk_axis") not in CUTOVER_READY_AXES:
            return False
        if _is_critical(finding):
            return True

    return gate_effect in set(finding.get("gate_effect", ()))


def _is_resolved(finding: Mapping[str, Any]) -> bool:
    return str(finding.get("status", "unresolved")) in NON_BLOCKING_STATUSES


def _is_critical(finding: Mapping[str, Any]) -> bool:
    return str(finding.get("severity")) == "critical"


def _missing_approvals(gate: str, context: GateContext) -> tuple[str, ...]:
    required_approval = REQUIRED_APPROVAL_BY_GATE[gate]
    if required_approval in set(context.approvals):
        return ()
    return (required_approval,)


def _unresolved_evidence_refs(context: GateContext) -> tuple[str, ...]:
    unresolved = set(context.required_evidence_refs) - set(context.resolved_evidence_refs)
    return tuple(sorted(unresolved))


def _unmet_prerequisites(gate: str, context: GateContext) -> tuple[str, ...]:
    checks = {
        "can_generate_final_plan": (
            ("discovery_artifacts_exist", context.discovery_artifacts_exist),
            ("compatibility_findings_produced", context.compatibility_findings_produced),
        ),
        "can_accept_validation": (
            ("validation_completed", context.validation_completed),
        ),
        "can_recommend_cutover": (
            ("validation_accepted", context.validation_accepted),
        ),
        "can_recommend_rollback": (
            ("rollback_criteria_exist", context.rollback_criteria_exist),
            ("blocked_validation_evidence_exists", context.blocked_validation_evidence_exists),
        ),
        "can_mark_ready": (
            ("validation_accepted", context.validation_accepted),
            ("final_runbook_published", context.final_runbook_published),
        ),
    }
    return tuple(name for name, passed in checks[gate] if not passed)
