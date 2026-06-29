"""Dependency-free API response helpers for the local workflow surface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


API_VERSION = "0.1.0"


def health_response() -> dict[str, str]:
    return {"status": "ok", "version": API_VERSION}


def scenarios_response(project_root: Path) -> dict[str, list[dict[str, Any]]]:
    scenarios_root = project_root / "fixtures" / "scenarios"
    scenarios = []
    for scenario_path in sorted(scenarios_root.glob("*/scenario.json")):
        scenario = json.loads(scenario_path.read_text())
        scenarios.append(
            {
                "scenario_id": scenario["scenario_id"],
                "description": scenario.get("description", ""),
                "critical_tables": scenario.get("critical_tables", []),
                "expected_results": scenario.get("expected_results"),
            }
        )
    return {"scenarios": scenarios}


def latest_manifest_response(project_root: Path) -> tuple[int, dict[str, Any]]:
    manifest_path = project_root / "artifacts" / "manifest.json"
    if not manifest_path.exists():
        return (
            404,
            {
                "error": {
                    "code": "artifact_manifest_not_found",
                    "message": "Run the workflow before requesting the latest manifest.",
                }
            },
        )
    return 200, json.loads(manifest_path.read_text())


def error_response(code: str, message: str, *, status: int = 400) -> tuple[int, dict[str, Any]]:
    return status, {"error": {"code": code, "message": message}}
