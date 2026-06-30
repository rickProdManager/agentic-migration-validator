"""Local JSON workflow run store."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

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

    workflow_path = run_dir / "workflow_run.json"
    audit_log_path = run_dir / "audit_log.json"
    manifest_path = run_dir / "manifest.json"
    workflow_path.write_text(json.dumps(dict(workflow_run), indent=2, sort_keys=True) + "\n")
    audit_log = {
        "audit_schema_version": "audit_event.v1",
        "workflow_run_id": workflow_run_id,
        "event_count": len(audit_events),
        "events": audit_events,
    }
    audit_log_path.write_text(json.dumps(audit_log, indent=2, sort_keys=True) + "\n")

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
        "audit_event_count": len(audit_events),
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


def run_store_root(project_root: Path) -> Path:
    configured = os.environ.get("RUN_DIR")
    if configured:
        path = Path(configured)
        return path if path.is_absolute() else project_root / path
    return project_root / "runs"


def _safe_workflow_run_id(workflow_run_id: str) -> bool:
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    return bool(workflow_run_id) and ".." not in workflow_run_id and set(workflow_run_id) <= allowed
