#!/usr/bin/env python3
"""Run the local fixture validation workflow and emit an API-shaped response."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_eval import default_scenario_ids
from scripts.write_artifacts import write_artifact_bundle
from tools.workflow import build_fixture_workflow_run, validate_workflow_run


def main(argv: list[str]) -> int:
    scenario_ids = argv[1:] or default_scenario_ids()
    workflow_run = run_fixture_workflow(scenario_ids)
    print(json.dumps(workflow_run, indent=2, sort_keys=True))
    return 0 if workflow_run["status"] == "completed" else 1


def run_fixture_workflow(scenario_ids: list[str]) -> dict:
    started_at = _utc_now()
    artifact_manifest = write_artifact_bundle(scenario_ids)
    completed_at = _utc_now()
    workflow_run = build_fixture_workflow_run(
        scenario_ids=scenario_ids,
        artifact_manifest=artifact_manifest,
        started_at=started_at,
        completed_at=completed_at,
    )
    issues = validate_workflow_run(workflow_run)
    if issues:
        workflow_run["status"] = "failed"
        workflow_run["workflow_validation"] = {
            "passed": False,
            "issues": [issue.to_dict() for issue in issues],
        }
    else:
        workflow_run["workflow_validation"] = {"passed": True, "issues": []}
    return workflow_run


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
