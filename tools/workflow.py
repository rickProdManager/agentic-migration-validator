"""Workflow response helpers for the local fixture validation flow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


WORKFLOW_VERSION = "fixture_validation_workflow.v1"
WORKSPACE_ID = "workspace_demo"
STEP_NAMES = (
    "run_deterministic_evals",
    "generate_runbook_drafts",
    "validate_artifact_bundle",
    "write_artifact_bundle",
)
KNOWN_STEP_STATUSES = {"completed", "failed", "skipped"}


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
    return {
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

    return tuple(issues)


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


def _artifact_refs(artifact_manifest: Mapping[str, Any]) -> list[str]:
    return [
        str(artifact.get("artifact_id"))
        for artifact in artifact_manifest.get("artifacts", [])
        if artifact.get("artifact_id")
    ]


def _workflow_run_id(started_at: str) -> str:
    compact = (
        started_at.replace("-", "")
        .replace(":", "")
        .replace(".", "")
        .replace("Z", "")
        .replace("T", "_")
    )
    return f"workflow.fixture_validation.{compact}"
