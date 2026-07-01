"""Workflow response helpers for the local fixture validation flow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from tools.audit import build_audit_event
from tools.transitions import (
    StageTransitionResult,
    build_transition_audit_event,
    evaluate_stage_transition,
)


WORKFLOW_VERSION = "fixture_validation_workflow.v1"
WORKSPACE_ID = "workspace_demo"
STEP_NAMES = (
    "run_deterministic_evals",
    "generate_runbook_drafts",
    "validate_artifact_bundle",
    "write_artifact_bundle",
)
KNOWN_STEP_STATUSES = {"completed", "failed", "skipped"}
STEP_AUDIT_ACTORS = {
    "run_deterministic_evals": ("eval_runner", "tool", "evaluation"),
    "generate_runbook_drafts": ("runbook_advisor", "advisor", "runbook"),
    "validate_artifact_bundle": ("artifact_validator", "system", "artifact_validation"),
    "write_artifact_bundle": ("artifact_writer", "system", "artifact_store"),
}
STEP_TARGET_STAGE = {
    "run_deterministic_evals": "evaluation",
    "generate_runbook_drafts": "runbook",
    "validate_artifact_bundle": "artifact_validation",
    "write_artifact_bundle": "artifacts_written",
}


@dataclass(frozen=True)
class WorkflowValidationIssue:
    path: str
    issue: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "issue": self.issue}


def build_fixture_workflow_run(
    *,
    scenario_ids: list[str],
    artifact_manifest: Mapping[str, Any],
    started_at: str,
    completed_at: str,
) -> dict[str, Any]:
    """Build the public workflow response for the fixture validation run."""

    passed = artifact_manifest.get("passed") is True
    status = "completed" if passed else "failed"
    workflow_run = {
        "workflow_run_id": _workflow_run_id(started_at),
        "workflow_version": WORKFLOW_VERSION,
        "workspace_id": WORKSPACE_ID,
        "status": status,
        "current_stage": "artifacts_written" if passed else "artifact_validation",
        "model_calls": "disabled",
        "scenario_ids": scenario_ids,
        "started_at": started_at,
        "completed_at": completed_at,
        "steps": _steps(passed),
        "artifact_refs": _artifact_refs(artifact_manifest),
        "artifact_manifest": dict(artifact_manifest),
    }
    workflow_run["stage_transitions"] = [
        result.to_dict()
        for result in _fixture_stage_transition_results(workflow_run)
    ]
    return workflow_run


def build_failed_fixture_workflow_run(
    *,
    scenario_ids: list[str],
    started_at: str,
    completed_at: str,
    failed_step: str,
    error_type: str,
) -> dict[str, Any]:
    """Build a persisted workflow response for failures before artifacts exist."""

    error_message = f"Workflow step {failed_step} failed before artifacts could be produced."
    failure = {
        "failed_step": failed_step,
        "error_code": f"workflow_step_failed:{failed_step}",
        "error_message": error_message,
        "error_type": error_type,
        "retryable": True,
    }
    workflow_run = {
        "workflow_run_id": _workflow_run_id(started_at),
        "workflow_version": WORKFLOW_VERSION,
        "workspace_id": WORKSPACE_ID,
        "status": "failed",
        "current_stage": STEP_TARGET_STAGE.get(failed_step, "evaluation"),
        "model_calls": "disabled",
        "scenario_ids": scenario_ids,
        "started_at": started_at,
        "completed_at": completed_at,
        "steps": _failed_steps(failed_step),
        "artifact_refs": [],
        "artifact_manifest": {
            "artifact_count": 0,
            "artifact_dir": "artifacts",
            "artifacts": [],
            "passed": False,
            "issues": [
                {
                    "path": f"workflow.steps.{failed_step}",
                    "issue": failure["error_code"],
                }
            ],
        },
        "failure": failure,
    }
    workflow_run["stage_transitions"] = [
        result.to_dict()
        for result in _fixture_stage_transition_results(workflow_run)
    ]
    return workflow_run


def validate_workflow_run(workflow_run: Mapping[str, Any]) -> tuple[WorkflowValidationIssue, ...]:
    issues = []
    required_fields = (
        "workflow_run_id",
        "workflow_version",
        "workspace_id",
        "status",
        "current_stage",
        "model_calls",
        "scenario_ids",
        "started_at",
        "completed_at",
        "steps",
        "stage_transitions",
        "artifact_refs",
        "artifact_manifest",
    )
    for field in required_fields:
        if field not in workflow_run:
            issues.append(WorkflowValidationIssue(field, "missing_field"))

    if workflow_run.get("workflow_version") != WORKFLOW_VERSION:
        issues.append(WorkflowValidationIssue("workflow_version", "invalid_workflow_version"))
    if workflow_run.get("status") not in {"completed", "failed"}:
        issues.append(WorkflowValidationIssue("status", "invalid_status"))
    if workflow_run.get("model_calls") != "disabled":
        issues.append(WorkflowValidationIssue("model_calls", "invalid_model_calls"))
    if not workflow_run.get("scenario_ids"):
        issues.append(WorkflowValidationIssue("scenario_ids", "missing_scenarios"))

    steps = workflow_run.get("steps")
    if not isinstance(steps, list) or not steps:
        issues.append(WorkflowValidationIssue("steps", "missing_steps"))
    else:
        step_names = {step.get("step") for step in steps if isinstance(step, Mapping)}
        if step_names != set(STEP_NAMES):
            issues.append(WorkflowValidationIssue("steps", "unexpected_steps"))
        for index, step in enumerate(steps):
            if not isinstance(step, Mapping):
                issues.append(WorkflowValidationIssue(f"steps.{index}", "invalid_step"))
                continue
            if step.get("status") not in KNOWN_STEP_STATUSES:
                issues.append(WorkflowValidationIssue(f"steps.{index}.status", "invalid_status"))

    manifest = workflow_run.get("artifact_manifest")
    if not isinstance(manifest, Mapping):
        issues.append(WorkflowValidationIssue("artifact_manifest", "missing_artifact_manifest"))
    else:
        manifest_passed = manifest.get("passed") is True
        if workflow_run.get("status") == "completed" and not manifest_passed:
            issues.append(WorkflowValidationIssue("artifact_manifest.passed", "manifest_not_passed"))
        if manifest_passed and not workflow_run.get("artifact_refs"):
            issues.append(WorkflowValidationIssue("artifact_refs", "missing_artifact_refs"))

    transitions = workflow_run.get("stage_transitions")
    if not isinstance(transitions, list) or not transitions:
        issues.append(WorkflowValidationIssue("stage_transitions", "missing_stage_transitions"))
    else:
        transition_allowed = [
            transition.get("allowed")
            for transition in transitions
            if isinstance(transition, Mapping)
        ]
        if workflow_run.get("status") == "completed" and not all(transition_allowed):
            issues.append(WorkflowValidationIssue("stage_transitions", "blocked_transition"))
        if workflow_run.get("status") == "failed" and all(transition_allowed):
            issues.append(WorkflowValidationIssue("stage_transitions", "missing_blocked_transition"))

    return tuple(issues)


def build_fixture_workflow_audit_log(
    workflow_run: Mapping[str, Any],
) -> list[dict[str, Any]]:
    workflow_run_id = str(workflow_run["workflow_run_id"])
    workspace_id = str(workflow_run["workspace_id"])
    scenario_ids = [str(value) for value in workflow_run.get("scenario_ids", [])]
    scenario_id = scenario_ids[0] if len(scenario_ids) == 1 else "fixture_suite"
    created_at = str(workflow_run.get("completed_at") or workflow_run.get("started_at"))
    events = []
    transition_results = {
        result.to_stage: result
        for result in _fixture_stage_transition_results(workflow_run)
    }
    for step in workflow_run.get("steps", []):
        step_name = str(step.get("step"))
        actor_name, actor_type, stage = STEP_AUDIT_ACTORS[step_name]
        transition_result = transition_results.get(STEP_TARGET_STAGE[step_name])
        if transition_result is not None:
            events.append(build_transition_audit_event(transition_result, workflow_run))
        step_status = str(step.get("status"))
        decision = _audit_decision(step_name, step_status)
        event = build_audit_event(
            audit_event_id=f"audit.{workflow_run_id}.{step_name}.v1",
            workflow_run_id=workflow_run_id,
            workspace_id=workspace_id,
            scenario_id=scenario_id,
            actor_name=actor_name,
            actor_type=actor_type,
            stage=stage,
            decision=decision,
            status=_audit_status(step_status),
            artifact_ids=_step_artifact_ids(step_name, workflow_run),
            created_at=created_at,
            input_summary=f"Executed workflow step {step_name}.",
            output_summary=f"Workflow step {step_name} ended with status {step_status}.",
            metadata={"step": step_name},
            **_step_error_fields(step_name, step_status, workflow_run),
        )
        events.append(event)
    return events


def _fixture_stage_transition_results(
    workflow_run: Mapping[str, Any],
) -> list[StageTransitionResult]:
    cursor = dict(workflow_run)
    cursor["current_stage"] = "not_started"
    results = []
    for to_stage in ("evaluation", "runbook", "artifact_validation", "artifacts_written"):
        result = evaluate_stage_transition(cursor, to_stage)
        results.append(result)
        if not result.allowed:
            break
        cursor["current_stage"] = to_stage
    return results


def _steps(passed: bool) -> list[dict[str, Any]]:
    if passed:
        statuses = {
            "run_deterministic_evals": "completed",
            "generate_runbook_drafts": "completed",
            "validate_artifact_bundle": "completed",
            "write_artifact_bundle": "completed",
        }
    else:
        statuses = {
            "run_deterministic_evals": "completed",
            "generate_runbook_drafts": "completed",
            "validate_artifact_bundle": "failed",
            "write_artifact_bundle": "skipped",
        }

    return [
        {
            "step": step,
            "status": statuses[step],
            "model_calls": "disabled",
        }
        for step in STEP_NAMES
    ]


def _failed_steps(failed_step: str) -> list[dict[str, Any]]:
    statuses = {}
    failed_seen = False
    for step in STEP_NAMES:
        if step == failed_step:
            statuses[step] = "failed"
            failed_seen = True
        elif failed_seen:
            statuses[step] = "skipped"
        else:
            statuses[step] = "completed"

    if failed_step not in statuses:
        statuses = {step: "skipped" for step in STEP_NAMES}
        statuses["run_deterministic_evals"] = "failed"

    return [
        {
            "step": step,
            "status": statuses[step],
            "model_calls": "disabled",
        }
        for step in STEP_NAMES
    ]


def _artifact_refs(artifact_manifest: Mapping[str, Any]) -> list[str]:
    return [
        str(artifact.get("artifact_id"))
        for artifact in artifact_manifest.get("artifacts", [])
        if artifact.get("artifact_id")
    ]


def _step_artifact_ids(
    step_name: str,
    workflow_run: Mapping[str, Any],
) -> list[str]:
    artifact_refs = list(workflow_run.get("artifact_refs", []))
    if step_name == "run_deterministic_evals":
        return [artifact_id for artifact_id in artifact_refs if ".eval_report." in artifact_id]
    if step_name == "generate_runbook_drafts":
        return [artifact_id for artifact_id in artifact_refs if ".runbook_draft." in artifact_id]
    if step_name in {"validate_artifact_bundle", "write_artifact_bundle"}:
        return artifact_refs
    return []


def _audit_decision(step_name: str, step_status: str) -> str:
    if step_name == "write_artifact_bundle" and step_status == "completed":
        return "artifact_generated"
    return "stage_completed"


def _audit_status(step_status: str) -> str:
    if step_status == "skipped":
        return "blocked"
    return step_status


def _step_error_fields(
    step_name: str,
    step_status: str,
    workflow_run: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if step_status != "failed":
        return {}
    failure = workflow_run.get("failure") if isinstance(workflow_run, Mapping) else None
    if isinstance(failure, Mapping) and failure.get("failed_step") == step_name:
        return {
            "error_code": str(failure["error_code"]),
            "error_message": str(failure["error_message"]),
            "error_type": str(failure.get("error_type", "workflow_step_failure")),
            "retryable": bool(failure.get("retryable", True)),
        }
    return {
        "error_code": f"workflow_step_failed:{step_name}",
        "error_message": f"Workflow step {step_name} failed.",
        "error_type": "workflow_step_failure",
        "retryable": True,
    }


def _workflow_run_id(started_at: str) -> str:
    compact = (
        started_at.replace("-", "")
        .replace(":", "")
        .replace(".", "")
        .replace("Z", "")
        .replace("T", "_")
    )
    return f"workflow.fixture_validation.{compact}"
