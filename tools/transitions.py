"""Deterministic workflow stage transition checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from tools.audit import build_audit_event


STAGES = (
    "not_started",
    "evaluation",
    "runbook",
    "artifact_validation",
    "artifacts_written",
)
ALLOWED_NEXT_STAGE = {
    "not_started": "evaluation",
    "evaluation": "runbook",
    "runbook": "artifact_validation",
    "artifact_validation": "artifacts_written",
}
REQUIRED_STEP_BY_TARGET_STAGE = {
    "evaluation": None,
    "runbook": "run_deterministic_evals",
    "artifact_validation": "generate_runbook_drafts",
    "artifacts_written": "validate_artifact_bundle",
}


@dataclass(frozen=True)
class StageTransitionResult:
    from_stage: str
    to_stage: str
    allowed: bool
    unmet_prerequisites: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_stage": self.from_stage,
            "to_stage": self.to_stage,
            "allowed": self.allowed,
            "unmet_prerequisites": list(self.unmet_prerequisites),
        }


def evaluate_stage_transition(
    workflow_run: Mapping[str, Any],
    to_stage: str,
) -> StageTransitionResult:
    from_stage = str(workflow_run.get("current_stage", "not_started"))
    unmet: list[str] = []

    if from_stage not in STAGES:
        unmet.append("unknown_current_stage")
    if to_stage not in STAGES:
        unmet.append("unknown_target_stage")

    expected_next = ALLOWED_NEXT_STAGE.get(from_stage)
    if expected_next != to_stage:
        unmet.append("transition_not_allowed")

    required_step = REQUIRED_STEP_BY_TARGET_STAGE.get(to_stage)
    if required_step and _step_status(workflow_run, required_step) != "completed":
        unmet.append(f"step_not_completed:{required_step}")

    if to_stage == "artifacts_written":
        manifest = workflow_run.get("artifact_manifest")
        if not isinstance(manifest, Mapping) or manifest.get("passed") is not True:
            unmet.append("artifact_manifest_not_passed")

    return StageTransitionResult(
        from_stage=from_stage,
        to_stage=to_stage,
        allowed=not unmet,
        unmet_prerequisites=tuple(unmet),
    )


def build_transition_audit_event(
    result: StageTransitionResult,
    workflow_run: Mapping[str, Any],
) -> dict[str, Any]:
    workflow_run_id = str(workflow_run.get("workflow_run_id"))
    return build_audit_event(
        audit_event_id=f"audit.{workflow_run_id}.transition.{result.from_stage}.{result.to_stage}.v1",
        workflow_run_id=workflow_run_id,
        workspace_id=str(workflow_run.get("workspace_id")),
        scenario_id=_scenario_id(workflow_run),
        actor_name="workflow_orchestrator",
        actor_type="system",
        stage=result.to_stage,
        decision="transition_allowed" if result.allowed else "transition_blocked",
        status="completed" if result.allowed else "blocked",
        created_at=str(workflow_run.get("completed_at") or workflow_run.get("started_at")),
        input_summary=f"Evaluated transition from {result.from_stage} to {result.to_stage}.",
        output_summary=(
            "Transition allowed."
            if result.allowed
            else f"Transition blocked: {', '.join(result.unmet_prerequisites)}."
        ),
        metadata=result.to_dict(),
    )


def _step_status(workflow_run: Mapping[str, Any], step_name: str) -> str | None:
    steps = workflow_run.get("steps")
    if not isinstance(steps, list):
        return None
    for step in steps:
        if isinstance(step, Mapping) and step.get("step") == step_name:
            return str(step.get("status"))
    return None


def _scenario_id(workflow_run: Mapping[str, Any]) -> str:
    scenario_ids = [str(value) for value in workflow_run.get("scenario_ids", [])]
    return scenario_ids[0] if len(scenario_ids) == 1 else "fixture_suite"
