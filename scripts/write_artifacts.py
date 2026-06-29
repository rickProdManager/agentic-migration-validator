#!/usr/bin/env python3
"""Write validated JSON artifacts for fixture scenarios."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.generate_runbook import generate_scenario_runbook
from scripts.run_eval import default_scenario_ids, run_evals
from tools.artifacts import (
    build_artifact,
    build_evidence_registry_payload,
    collect_evidence_refs,
    eval_report_evidence_refs,
    validate_artifact_bundle,
    write_json_artifacts,
)


def main(argv: list[str]) -> int:
    scenario_ids = argv[1:] or default_scenario_ids()
    manifest = write_artifact_bundle(scenario_ids)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if manifest["passed"] else 1


def write_artifact_bundle(
    scenario_ids: list[str],
    output_root: Path | None = None,
) -> dict[str, Any]:
    output_root = output_root or _artifact_root()
    artifacts = build_artifact_bundle(scenario_ids)
    issues = validate_artifact_bundle(artifacts)
    if issues:
        return {
            "artifact_dir": str(output_root),
            "passed": False,
            "issues": [issue.to_dict() for issue in issues],
        }

    written = write_json_artifacts(output_root, artifacts)
    manifest = {
        "artifact_dir": str(output_root),
        "artifact_count": len(written),
        "passed": True,
        "artifacts": written,
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    return manifest


def build_artifact_bundle(scenario_ids: list[str]) -> dict[str, dict[str, Any]]:
    eval_report = run_evals(scenario_ids)
    artifacts = {
        "eval_report.json": build_artifact(
            eval_report,
            artifact_id="artifact.eval_report.fixture_suite.v1",
            artifact_type="eval_report",
            scenario_id="fixture_suite",
            producer="eval_runner",
            model_calls=eval_report["model_calls"],
            evidence_refs=eval_report_evidence_refs(eval_report),
            status="accepted" if eval_report["passed"] else "rejected",
        )
    }

    for scenario_id in scenario_ids:
        runbook = generate_scenario_runbook(scenario_id)
        artifacts[f"scenarios/{scenario_id}/runbook.json"] = build_artifact(
            runbook,
            artifact_id=f"artifact.runbook_draft.{scenario_id}.v1",
            artifact_type="runbook",
            scenario_id=scenario_id,
            producer="runbook_advisor",
            model_calls=runbook.get("model_calls", "disabled"),
            evidence_refs=collect_evidence_refs(runbook),
            status="draft",
        )

    registry_payload = build_evidence_registry_payload(artifacts)
    artifacts["evidence_registry.json"] = build_artifact(
        registry_payload,
        artifact_id="artifact.evidence_registry.fixture_suite.v1",
        artifact_type="evidence_registry",
        scenario_id="fixture_suite",
        producer="artifact_writer",
        model_calls="disabled",
        evidence_refs=[entry["evidence_ref"] for entry in registry_payload["entries"]],
        status="accepted",
    )

    return artifacts


def _artifact_root() -> Path:
    configured = os.environ.get("ARTIFACT_DIR")
    if configured:
        path = Path(configured)
        return path if path.is_absolute() else PROJECT_ROOT / path
    return PROJECT_ROOT / "artifacts"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
