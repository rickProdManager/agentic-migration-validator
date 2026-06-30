"""Local JSON workflow run store."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Iterable, Mapping

from tools.approvals import effective_approvals, pending_approvals, validate_approval_record
from tools.audit import validate_audit_log
from tools.workflow import validate_workflow_run


RUN_STORE_VERSION = "local_run_store.v1"


def write_run_state(
    project_root: Path,
    workflow_run: Mapping[str, Any],
    audit_events: Iterable[Mapping[str, Any]],
    *,
    output_root: Path | None = None,
) -> dict[str, Any]:
    workflow_issues = validate_workflow_run(workflow_run)
    if workflow_issues:
        return {
            "run_store_version": RUN_STORE_VERSION,
            "passed": False,
            "issues": [issue.to_dict() for issue in workflow_issues],
        }

    audit_events = list(audit_events)
    audit_issues = validate_audit_log(audit_events)
    if audit_issues:
        return {
            "run_store_version": RUN_STORE_VERSION,
            "passed": False,
            "issues": [issue.to_dict() for issue in audit_issues],
        }

    run_root = output_root or run_store_root(project_root)
    workflow_run_id = str(workflow_run["workflow_run_id"])
    run_dir = run_root / workflow_run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    persisted_workflow_run = _snapshot_workflow_artifacts(project_root, run_dir, workflow_run)

    workflow_path = run_dir / "workflow_run.json"
    audit_log_path = run_dir / "audit_log.json"
    approvals_path = run_dir / "approvals.json"
    manifest_path = run_dir / "manifest.json"
    workflow_path.write_text(json.dumps(persisted_workflow_run, indent=2, sort_keys=True) + "\n")
    audit_log = {
        "audit_schema_version": "audit_event.v1",
        "workflow_run_id": workflow_run_id,
        "event_count": len(audit_events),
        "events": audit_events,
    }
    audit_log_path.write_text(json.dumps(audit_log, indent=2, sort_keys=True) + "\n")
    approval_log = _empty_approval_log(workflow_run_id)
    approvals_path.write_text(json.dumps(approval_log, indent=2, sort_keys=True) + "\n")

    manifest = {
        "run_store_version": RUN_STORE_VERSION,
        "passed": True,
        "workflow_run_id": workflow_run_id,
        "workspace_id": workflow_run.get("workspace_id"),
        "status": workflow_run.get("status"),
        "current_stage": workflow_run.get("current_stage"),
        "started_at": workflow_run.get("started_at"),
        "completed_at": workflow_run.get("completed_at"),
        "workflow_run_path": str(workflow_path),
        "audit_log_path": str(audit_log_path),
        "approvals_path": str(approvals_path),
        "audit_event_count": len(audit_events),
        "approval_count": 0,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "latest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def latest_run_manifest(
    project_root: Path,
    *,
    output_root: Path | None = None,
) -> dict[str, Any] | None:
    path = (output_root or run_store_root(project_root)) / "latest.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def list_run_manifests(
    project_root: Path,
    *,
    output_root: Path | None = None,
) -> list[dict[str, Any]]:
    run_root = output_root or run_store_root(project_root)
    if not run_root.exists():
        return []

    manifests = []
    for manifest_path in sorted(run_root.glob("*/manifest.json")):
        try:
            manifest = json.loads(manifest_path.read_text())
        except json.JSONDecodeError:
            continue
        if _safe_workflow_run_id(str(manifest.get("workflow_run_id", ""))):
            manifests.append(manifest)

    return sorted(
        manifests,
        key=lambda manifest: (
            str(manifest.get("completed_at") or ""),
            str(manifest.get("started_at") or ""),
            str(manifest.get("workflow_run_id") or ""),
        ),
        reverse=True,
    )


def read_workflow_run(
    project_root: Path,
    workflow_run_id: str,
    *,
    output_root: Path | None = None,
) -> dict[str, Any] | None:
    if not _safe_workflow_run_id(workflow_run_id):
        return None
    path = (output_root or run_store_root(project_root)) / workflow_run_id / "workflow_run.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def read_audit_log(
    project_root: Path,
    workflow_run_id: str,
    *,
    output_root: Path | None = None,
) -> dict[str, Any] | None:
    if not _safe_workflow_run_id(workflow_run_id):
        return None
    path = (output_root or run_store_root(project_root)) / workflow_run_id / "audit_log.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def read_approval_log(
    project_root: Path,
    workflow_run_id: str,
    *,
    output_root: Path | None = None,
) -> dict[str, Any] | None:
    if not _safe_workflow_run_id(workflow_run_id):
        return None
    path = (output_root or run_store_root(project_root)) / workflow_run_id / "approvals.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def append_approval_record(
    project_root: Path,
    workflow_run_id: str,
    approval_record: Mapping[str, Any],
    audit_event: Mapping[str, Any],
    *,
    output_root: Path | None = None,
) -> dict[str, Any]:
    if not _safe_workflow_run_id(workflow_run_id):
        return {
            "run_store_version": RUN_STORE_VERSION,
            "passed": False,
            "issues": [{"path": "workflow_run_id", "issue": "invalid_workflow_run_id"}],
        }

    run_root = output_root or run_store_root(project_root)
    run_dir = run_root / workflow_run_id
    if not run_dir.exists():
        return {
            "run_store_version": RUN_STORE_VERSION,
            "passed": False,
            "issues": [{"path": "workflow_run_id", "issue": "workflow_run_not_found"}],
        }

    approval_issues = validate_approval_record(approval_record)
    if approval_issues:
        return {
            "run_store_version": RUN_STORE_VERSION,
            "passed": False,
            "issues": [issue.to_dict() for issue in approval_issues],
        }

    audit_log = read_audit_log(project_root, workflow_run_id, output_root=run_root)
    if audit_log is None:
        return {
            "run_store_version": RUN_STORE_VERSION,
            "passed": False,
            "issues": [{"path": "audit_log", "issue": "audit_log_not_found"}],
        }

    approval_log = read_approval_log(project_root, workflow_run_id, output_root=run_root)
    if approval_log is None:
        approval_log = _empty_approval_log(workflow_run_id)

    approvals = list(approval_log.get("approvals", []))
    approvals.append(dict(approval_record))
    updated_approval_log = _approval_log(workflow_run_id, approvals)

    events = list(audit_log.get("events", []))
    events.append(dict(audit_event))
    audit_issues = validate_audit_log(events)
    if audit_issues:
        return {
            "run_store_version": RUN_STORE_VERSION,
            "passed": False,
            "issues": [issue.to_dict() for issue in audit_issues],
        }

    updated_audit_log = {
        "audit_schema_version": "audit_event.v1",
        "workflow_run_id": workflow_run_id,
        "event_count": len(events),
        "events": events,
    }
    approvals_path = run_dir / "approvals.json"
    audit_log_path = run_dir / "audit_log.json"
    approvals_path.write_text(json.dumps(updated_approval_log, indent=2, sort_keys=True) + "\n")
    audit_log_path.write_text(json.dumps(updated_audit_log, indent=2, sort_keys=True) + "\n")
    _update_run_manifest(run_dir, audit_event_count=len(events), approval_count=len(approvals))
    return {
        "run_store_version": RUN_STORE_VERSION,
        "passed": True,
        "workflow_run_id": workflow_run_id,
        "approval_count": len(approvals),
        "audit_event_count": len(events),
        "approval_id": approval_record.get("approval_id"),
    }


def run_store_root(project_root: Path) -> Path:
    configured = os.environ.get("RUN_DIR")
    if configured:
        path = Path(configured)
        return path if path.is_absolute() else project_root / path
    return project_root / "runs"


def _safe_workflow_run_id(workflow_run_id: str) -> bool:
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    return bool(workflow_run_id) and ".." not in workflow_run_id and set(workflow_run_id) <= allowed


def _empty_approval_log(workflow_run_id: str) -> dict[str, Any]:
    return _approval_log(workflow_run_id, [])


def _approval_log(
    workflow_run_id: str,
    approvals: list[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "approval_schema_version": "approval_record.v1",
        "workflow_run_id": workflow_run_id,
        "approval_count": len(approvals),
        "effective_approvals": list(effective_approvals(approvals)),
        "pending_approvals": list(pending_approvals(approvals)),
        "approvals": [dict(approval) for approval in approvals],
    }


def _update_run_manifest(
    run_dir: Path,
    *,
    audit_event_count: int,
    approval_count: int,
) -> None:
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text())
    manifest["audit_event_count"] = audit_event_count
    manifest["approval_count"] = approval_count
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    latest_path = run_dir.parent / "latest.json"
    if latest_path.exists():
        latest = json.loads(latest_path.read_text())
        if latest.get("workflow_run_id") == manifest.get("workflow_run_id"):
            latest["audit_event_count"] = audit_event_count
            latest["approval_count"] = approval_count
            latest_path.write_text(json.dumps(latest, indent=2, sort_keys=True) + "\n")


def _snapshot_workflow_artifacts(
    project_root: Path,
    run_dir: Path,
    workflow_run: Mapping[str, Any],
) -> dict[str, Any]:
    artifact_manifest = workflow_run.get("artifact_manifest")
    if not isinstance(artifact_manifest, Mapping):
        return dict(workflow_run)

    artifacts_root = (project_root / "artifacts").resolve()
    snapshot_root = run_dir / "artifacts"
    updated_artifacts = []
    for artifact in artifact_manifest.get("artifacts", []):
        artifact_entry = dict(artifact)
        raw_path = artifact_entry.get("path")
        if not raw_path:
            updated_artifacts.append(artifact_entry)
            continue

        artifact_path = Path(raw_path)
        if not artifact_path.is_absolute():
            artifact_path = project_root / artifact_path
        artifact_path = artifact_path.resolve()
        if not artifact_path.exists() or not _is_relative_to(artifact_path, artifacts_root):
            updated_artifacts.append(artifact_entry)
            continue

        relative_path = artifact_path.relative_to(artifacts_root)
        snapshot_path = snapshot_root / relative_path
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(artifact_path, snapshot_path)
        artifact_entry["path"] = str(snapshot_path)
        updated_artifacts.append(artifact_entry)

    updated_manifest = dict(artifact_manifest)
    updated_manifest["artifact_dir"] = str(snapshot_root)
    updated_manifest["artifacts"] = updated_artifacts
    updated_workflow_run = dict(workflow_run)
    updated_workflow_run["artifact_manifest"] = updated_manifest
    return updated_workflow_run


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
