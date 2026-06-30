"""Approval-aware readiness views derived from persisted workflow state."""

from __future__ import annotations

from typing import Any, Mapping

from tools.approvals import effective_approvals, pending_approvals
from tools.gatekeeper import GateContext, evaluate_gate


READINESS_GATES = (
    "can_generate_final_plan",
    "can_accept_validation",
    "can_recommend_cutover",
    "can_recommend_rollback",
    "can_mark_ready",
)


def build_readiness_view(
    workflow_run: Mapping[str, Any],
    approval_log: Mapping[str, Any],
    eval_report: Mapping[str, Any],
) -> dict[str, Any]:
    approvals = effective_approvals(approval_log.get("approvals", []))
    pending = pending_approvals(approval_log.get("approvals", []))
    scenarios = [
        _scenario_readiness(workflow_run, scenario, approvals)
        for scenario in eval_report.get("scenarios", [])
        if isinstance(scenario, Mapping)
    ]
    return {
        "workflow_run_id": workflow_run.get("workflow_run_id"),
        "workspace_id": workflow_run.get("workspace_id"),
        "status": workflow_run.get("status"),
        "current_stage": workflow_run.get("current_stage"),
        "approval_state": {
            "approval_count": approval_log.get("approval_count", 0),
            "effective_approvals": list(approvals),
            "pending_approvals": list(pending),
        },
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
    }


def _scenario_readiness(
    workflow_run: Mapping[str, Any],
    scenario: Mapping[str, Any],
    approvals: tuple[str, ...],
) -> dict[str, Any]:
    scenario_id = str(scenario.get("scenario_id"))
    findings = [
        *scenario.get("validation_findings", []),
        *scenario.get("schema_findings", []),
    ]
    context = _gate_context(workflow_run, scenario_id, findings, approvals)
    gates = {
        gate: evaluate_gate(gate, findings, context).to_dict()
        for gate in READINESS_GATES
    }
    blocked_gates = [
        gate
        for gate, result in gates.items()
        if not result["allowed"]
    ]
    return {
        "scenario_id": scenario_id,
        "context": _context_payload(context),
        "gate_results": gates,
        "blocked_gates": blocked_gates,
        "cutover_ready": gates["can_recommend_cutover"]["allowed"],
        "migration_ready": gates["can_mark_ready"]["allowed"],
    }


def _gate_context(
    workflow_run: Mapping[str, Any],
    scenario_id: str,
    findings: list[Mapping[str, Any]],
    approvals: tuple[str, ...],
) -> GateContext:
    validation_accepted = "validation_acceptance" in approvals
    return GateContext(
        validation_completed=_step_completed(workflow_run, "run_deterministic_evals"),
        validation_accepted=validation_accepted,
        discovery_artifacts_exist=_artifact_manifest_passed(workflow_run),
        compatibility_findings_produced=True,
        rollback_criteria_exist=False,
        blocked_validation_evidence_exists=bool(findings),
        final_runbook_published=_has_runbook_artifact(workflow_run, scenario_id),
        approvals=approvals,
        checked_at=str(workflow_run.get("completed_at")) if workflow_run.get("completed_at") else None,
    )


def _context_payload(context: GateContext) -> dict[str, Any]:
    return {
        "validation_completed": context.validation_completed,
        "validation_accepted": context.validation_accepted,
        "discovery_artifacts_exist": context.discovery_artifacts_exist,
        "compatibility_findings_produced": context.compatibility_findings_produced,
        "rollback_criteria_exist": context.rollback_criteria_exist,
        "blocked_validation_evidence_exists": context.blocked_validation_evidence_exists,
        "final_runbook_published": context.final_runbook_published,
        "approvals": list(context.approvals),
        "checked_at": context.checked_at,
    }


def _step_completed(workflow_run: Mapping[str, Any], step_name: str) -> bool:
    steps = workflow_run.get("steps")
    if not isinstance(steps, list):
        return False
    return any(
        isinstance(step, Mapping)
        and step.get("step") == step_name
        and step.get("status") == "completed"
        for step in steps
    )


def _artifact_manifest_passed(workflow_run: Mapping[str, Any]) -> bool:
    manifest = workflow_run.get("artifact_manifest")
    return isinstance(manifest, Mapping) and manifest.get("passed") is True


def _has_runbook_artifact(workflow_run: Mapping[str, Any], scenario_id: str) -> bool:
    return any(
        artifact_id == f"artifact.runbook_draft.{scenario_id}.v1"
        for artifact_id in workflow_run.get("artifact_refs", [])
    )
