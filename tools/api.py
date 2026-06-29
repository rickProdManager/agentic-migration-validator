"""Dependency-free API response helpers for the local workflow surface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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


def latest_manifest_response(project_root: Path) -> tuple[int, dict[str, Any]]:
    status, manifest = _load_manifest(project_root)
    if status != 200:
        return status, manifest
    return 200, manifest


def artifact_response(project_root: Path, artifact_id: str) -> tuple[int, dict[str, Any]]:
    status, manifest = _load_manifest(project_root)
    if status != 200:
        return status, manifest

    artifact_entry = _manifest_artifact(manifest, artifact_id)
    if artifact_entry is None:
        return error_response(
            "artifact_not_found",
            f"No artifact found for artifact_id {artifact_id!r}.",
            status=404,
        )

    status, artifact = _read_artifact_file(project_root, artifact_entry)
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


def evidence_response(project_root: Path, evidence_ref: str) -> tuple[int, dict[str, Any]]:
    registry_path = project_root / "artifacts" / "evidence_registry.json"
    if not registry_path.exists():
        return error_response(
            "evidence_registry_not_found",
            "Run the workflow before requesting evidence references.",
            status=404,
        )

    registry = json.loads(registry_path.read_text())
    for entry in registry.get("entries", []):
        if entry.get("evidence_ref") == evidence_ref:
            return 200, {"evidence_ref": evidence_ref, "entry": entry}

    return error_response(
        "evidence_ref_not_found",
        f"No evidence registry entry found for evidence_ref {evidence_ref!r}.",
        status=404,
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


def _read_artifact_file(
    project_root: Path,
    artifact_entry: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    raw_path = artifact_entry.get("path")
    if not raw_path:
        return error_response(
            "artifact_path_missing",
            "Artifact manifest entry does not include a path.",
            status=500,
        )

    artifacts_root = (project_root / "artifacts").resolve()
    artifact_path = Path(raw_path)
    if not artifact_path.is_absolute():
        artifact_path = project_root / artifact_path
    artifact_path = artifact_path.resolve()

    if not _is_relative_to(artifact_path, artifacts_root):
        return error_response(
            "artifact_path_outside_store",
            "Artifact manifest entry points outside the artifact store.",
            status=500,
        )
    if not artifact_path.exists():
        return error_response(
            "artifact_file_not_found",
            f"Artifact file does not exist: {artifact_path}",
            status=404,
        )

    return 200, json.loads(artifact_path.read_text())


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
