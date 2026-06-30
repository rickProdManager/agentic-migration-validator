"""Dependency-free API response helpers for the local workflow surface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from tools.approvals import build_approval_audit_event, build_approval_record
from tools.artifacts import resolve_evidence_ref
from tools.readiness import build_readiness_view
from tools.run_store import (
    append_approval_record,
    latest_run_manifest,
    list_run_manifests,
    read_audit_log,
    read_approval_log,
    read_workflow_run,
    run_store_root,
)


API_VERSION = "0.1.0"


def health_response() -> dict[str, str]:
    return {"status": "ok", "version": API_VERSION}


def scenarios_response(project_root: Path) -> dict[str, list[dict[str, Any]]]:
    scenarios = []
    for scenario in load_scenarios(project_root):
        scenarios.append(
            {
                "scenario_id": scenario["scenario_id"],
                "description": scenario.get("description", ""),
                "critical_tables": scenario.get("critical_tables", []),
                "expected_results": scenario.get("expected_results"),
            }
        )
    return {"scenarios": scenarios}


def load_scenarios(project_root: Path) -> list[dict[str, Any]]:
    scenarios_root = project_root / "fixtures" / "scenarios"
    return [
        json.loads(scenario_path.read_text())
        for scenario_path in sorted(scenarios_root.glob("*/scenario.json"))
    ]


def validate_requested_scenarios(
    project_root: Path,
    scenario_ids: list[str],
) -> tuple[int, dict[str, Any]] | None:
    known_scenario_ids = {scenario["scenario_id"] for scenario in load_scenarios(project_root)}
    unknown = [scenario_id for scenario_id in scenario_ids if scenario_id not in known_scenario_ids]
    if not unknown:
        return None

    return error_response(
        "unknown_scenario",
        f"Unknown scenario_id: {unknown[0]}",
        status=400,
    )


def workflow_run_failed_response(error: Exception) -> tuple[int, dict[str, Any]]:
    status, payload = error_response(
        "workflow_run_failed",
        "Workflow run failed. Confirm Docker fixture containers are running and retry.",
        status=500,
    )
    payload["error"]["details"] = {
        "exception": error.__class__.__name__,
        "recovery_hint": "Run make db-up, then retry the workflow launch.",
    }
    return status, payload


def latest_manifest_response(project_root: Path) -> tuple[int, dict[str, Any]]:
    status, manifest = _load_manifest(project_root)
    if status != 200:
        return status, manifest
    return 200, manifest


def artifact_response(project_root: Path, artifact_id: str) -> tuple[int, dict[str, Any]]:
    status, manifest = _load_manifest(project_root)
    if status != 200:
        return status, manifest

    return _artifact_from_manifest_response(project_root, manifest, artifact_id)


def evidence_response(project_root: Path, evidence_ref: str) -> tuple[int, dict[str, Any]]:
    registry_path = project_root / "artifacts" / "evidence_registry.json"
    if not registry_path.exists():
        return error_response(
            "evidence_registry_not_found",
            "Run the workflow before requesting evidence references.",
            status=404,
        )

    registry = json.loads(registry_path.read_text())
    entry = resolve_evidence_ref(registry, evidence_ref)
    if entry is not None:
        return 200, {"evidence_ref": evidence_ref, "entry": entry}

    return error_response(
        "evidence_ref_not_found",
        f"No evidence registry entry found for evidence_ref {evidence_ref!r}.",
        status=404,
    )


def latest_workflow_run_response(project_root: Path) -> tuple[int, dict[str, Any]]:
    manifest = latest_run_manifest(project_root)
    if manifest is None:
        return error_response(
            "workflow_run_not_found",
            "Run the workflow before requesting workflow state.",
            status=404,
        )

    workflow_run_id = str(manifest.get("workflow_run_id", ""))
    workflow_run = read_workflow_run(project_root, workflow_run_id)
    if workflow_run is None:
        return error_response(
            "workflow_run_not_found",
            f"No workflow run found for workflow_run_id {workflow_run_id!r}.",
            status=404,
        )
    return 200, {"run_manifest": manifest, "workflow_run": workflow_run}


def workflow_runs_response(project_root: Path) -> tuple[int, dict[str, Any]]:
    manifests = list_run_manifests(project_root)
    latest = latest_run_manifest(project_root) or {}
    latest_workflow_run_id = latest.get("workflow_run_id")
    return (
        200,
        {
            "run_count": len(manifests),
            "latest_workflow_run_id": latest_workflow_run_id,
            "runs": [
                {
                    **manifest,
                    "is_latest": manifest.get("workflow_run_id") == latest_workflow_run_id,
                }
                for manifest in manifests
            ],
        },
    )


def workflow_run_response(
    project_root: Path,
    workflow_run_id: str,
) -> tuple[int, dict[str, Any]]:
    workflow_run = read_workflow_run(project_root, workflow_run_id)
    if workflow_run is None:
        return error_response(
            "workflow_run_not_found",
            f"No workflow run found for workflow_run_id {workflow_run_id!r}.",
            status=404,
        )
    return 200, {"workflow_run": workflow_run}


def workflow_artifact_response(
    project_root: Path,
    workflow_run_id: str,
    artifact_id: str,
) -> tuple[int, dict[str, Any]]:
    workflow_run = read_workflow_run(project_root, workflow_run_id)
    if workflow_run is None:
        return error_response(
            "workflow_run_not_found",
            f"No workflow run found for workflow_run_id {workflow_run_id!r}.",
            status=404,
        )

    manifest = workflow_run.get("artifact_manifest")
    if not isinstance(manifest, Mapping):
        return error_response(
            "artifact_manifest_not_found",
            "Workflow run does not include an artifact manifest.",
            status=404,
        )

    return _artifact_from_manifest_response(
        project_root,
        dict(manifest),
        artifact_id,
        allow_run_store=True,
    )


def workflow_evidence_response(
    project_root: Path,
    workflow_run_id: str,
    evidence_ref: str,
) -> tuple[int, dict[str, Any]]:
    workflow_run = read_workflow_run(project_root, workflow_run_id)
    if workflow_run is None:
        return error_response(
            "workflow_run_not_found",
            f"No workflow run found for workflow_run_id {workflow_run_id!r}.",
            status=404,
        )

    manifest = workflow_run.get("artifact_manifest")
    if not isinstance(manifest, Mapping):
        return error_response(
            "evidence_registry_not_found",
            "Workflow run does not include an artifact manifest.",
            status=404,
        )

    artifact_entry = _first_manifest_artifact(dict(manifest), "artifact.evidence_registry.")
    if artifact_entry is None:
        return error_response(
            "evidence_registry_not_found",
            "Workflow run does not include an evidence registry artifact.",
            status=404,
        )

    status, registry = _read_artifact_file(
        project_root,
        artifact_entry,
        allow_run_store=True,
    )
    if status != 200:
        return status, registry

    entry = resolve_evidence_ref(registry, evidence_ref)
    if entry is not None:
        return 200, {"evidence_ref": evidence_ref, "entry": entry}

    return error_response(
        "evidence_ref_not_found",
        f"No evidence registry entry found for evidence_ref {evidence_ref!r}.",
        status=404,
    )


def workflow_audit_response(
    project_root: Path,
    workflow_run_id: str,
) -> tuple[int, dict[str, Any]]:
    audit_log = read_audit_log(project_root, workflow_run_id)
    if audit_log is None:
        return error_response(
            "audit_log_not_found",
            f"No audit log found for workflow_run_id {workflow_run_id!r}.",
            status=404,
        )
    return 200, audit_log


def workflow_approvals_response(
    project_root: Path,
    workflow_run_id: str,
) -> tuple[int, dict[str, Any]]:
    approval_log = read_approval_log(project_root, workflow_run_id)
    if approval_log is None:
        return error_response(
            "approval_log_not_found",
            f"No approval log found for workflow_run_id {workflow_run_id!r}.",
            status=404,
        )
    return 200, approval_log


def workflow_readiness_response(
    project_root: Path,
    workflow_run_id: str,
) -> tuple[int, dict[str, Any]]:
    workflow_run = read_workflow_run(project_root, workflow_run_id)
    if workflow_run is None:
        return error_response(
            "workflow_run_not_found",
            f"No workflow run found for workflow_run_id {workflow_run_id!r}.",
            status=404,
        )

    approval_log = read_approval_log(project_root, workflow_run_id)
    if approval_log is None:
        return error_response(
            "approval_log_not_found",
            f"No approval log found for workflow_run_id {workflow_run_id!r}.",
            status=404,
        )

    status, eval_report = _workflow_eval_report(project_root, workflow_run)
    if status != 200:
        return status, eval_report

    return 200, build_readiness_view(workflow_run, approval_log, eval_report)


def submit_workflow_approval_response(
    project_root: Path,
    workflow_run_id: str,
    payload: Mapping[str, Any],
) -> tuple[int, dict[str, Any]]:
    workflow_run = read_workflow_run(project_root, workflow_run_id)
    if workflow_run is None:
        return error_response(
            "workflow_run_not_found",
            f"No workflow run found for workflow_run_id {workflow_run_id!r}.",
            status=404,
        )

    evidence_refs = payload.get("evidence_refs", [])
    if not isinstance(evidence_refs, list):
        return error_response(
            "invalid_approval",
            "evidence_refs must be a JSON array.",
            status=400,
        )

    try:
        approval = build_approval_record(
            workflow_run_id=workflow_run_id,
            workspace_id=str(workflow_run.get("workspace_id")),
            scenario_id=str(payload.get("scenario_id") or _workflow_scenario_id(workflow_run)),
            gate=str(payload.get("gate", "")),
            actor=str(payload.get("actor", "")),
            decision=str(payload.get("decision", "")),
            evidence_refs=evidence_refs,
            notes=payload.get("notes"),
        )
    except ValueError as error:
        return error_response("invalid_approval", str(error), status=400)

    audit_event = build_approval_audit_event(approval)
    result = append_approval_record(project_root, workflow_run_id, approval, audit_event)
    if result.get("passed") is not True:
        return (
            400,
            {
                "error": {
                    "code": "approval_validation_failed",
                    "message": "Approval record failed validation.",
                    "details": {"issues": result.get("issues", [])},
                }
            },
        )

    approval_log = read_approval_log(project_root, workflow_run_id) or {}
    return (
        201,
        {
            "approval": approval,
            "audit_event": audit_event,
            "run_state": result,
            "effective_approvals": approval_log.get("effective_approvals", []),
            "pending_approvals": approval_log.get("pending_approvals", []),
        },
    )


def error_response(code: str, message: str, *, status: int = 400) -> tuple[int, dict[str, Any]]:
    return status, {"error": {"code": code, "message": message}}


def _load_manifest(project_root: Path) -> tuple[int, dict[str, Any]]:
    manifest_path = project_root / "artifacts" / "manifest.json"
    if not manifest_path.exists():
        return error_response(
            "artifact_manifest_not_found",
            "Run the workflow before requesting the latest manifest.",
            status=404,
        )
    return 200, json.loads(manifest_path.read_text())


def _manifest_artifact(
    manifest: dict[str, Any],
    artifact_id: str,
) -> dict[str, Any] | None:
    for artifact in manifest.get("artifacts", []):
        if artifact.get("artifact_id") == artifact_id:
            return artifact
    return None


def _first_manifest_artifact(
    manifest: dict[str, Any],
    artifact_id_prefix: str,
) -> dict[str, Any] | None:
    for artifact in manifest.get("artifacts", []):
        artifact_id = str(artifact.get("artifact_id", ""))
        if artifact_id.startswith(artifact_id_prefix):
            return artifact
    return None


def _artifact_from_manifest_response(
    project_root: Path,
    manifest: dict[str, Any],
    artifact_id: str,
    *,
    allow_run_store: bool = False,
) -> tuple[int, dict[str, Any]]:
    artifact_entry = _manifest_artifact(manifest, artifact_id)
    if artifact_entry is None:
        return error_response(
            "artifact_not_found",
            f"No artifact found for artifact_id {artifact_id!r}.",
            status=404,
        )

    status, artifact = _read_artifact_file(
        project_root,
        artifact_entry,
        allow_run_store=allow_run_store,
    )
    if status != 200:
        return status, artifact

    return (
        200,
        {
            "artifact_id": artifact_id,
            "path": artifact_entry.get("path"),
            "content_hash": artifact_entry.get("content_hash"),
            "metadata": artifact.get("metadata", {}),
            "content": artifact,
        },
    )


def _read_artifact_file(
    project_root: Path,
    artifact_entry: dict[str, Any],
    *,
    allow_run_store: bool = False,
) -> tuple[int, dict[str, Any]]:
    raw_path = artifact_entry.get("path")
    if not raw_path:
        return error_response(
            "artifact_path_missing",
            "Artifact manifest entry does not include a path.",
            status=500,
        )

    allowed_roots = [(project_root / "artifacts").resolve()]
    if allow_run_store:
        allowed_roots.append(run_store_root(project_root).resolve())
    artifact_path = Path(raw_path)
    if not artifact_path.is_absolute():
        artifact_path = project_root / artifact_path
    artifact_path = artifact_path.resolve()

    if not any(_is_relative_to(artifact_path, root) for root in allowed_roots):
        return error_response(
            "artifact_path_outside_store",
            "Artifact manifest entry points outside allowed artifact stores.",
            status=500,
        )
    if not artifact_path.exists():
        return error_response(
            "artifact_file_not_found",
            f"Artifact file does not exist: {artifact_path}",
            status=404,
        )

    return 200, json.loads(artifact_path.read_text())


def _workflow_eval_report(
    project_root: Path,
    workflow_run: Mapping[str, Any],
) -> tuple[int, dict[str, Any]]:
    manifest = workflow_run.get("artifact_manifest")
    if not isinstance(manifest, Mapping):
        return error_response(
            "eval_report_not_found",
            "Workflow run does not include an artifact manifest.",
            status=404,
        )

    artifact_entry = _manifest_artifact(dict(manifest), "artifact.eval_report.fixture_suite.v1")
    if artifact_entry is None:
        return error_response(
            "eval_report_not_found",
            "Workflow run does not include an eval report artifact.",
            status=404,
        )
    return _read_artifact_file(project_root, artifact_entry, allow_run_store=True)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _workflow_scenario_id(workflow_run: Mapping[str, Any]) -> str:
    scenario_ids = [str(value) for value in workflow_run.get("scenario_ids", [])]
    return scenario_ids[0] if len(scenario_ids) == 1 else "fixture_suite"
