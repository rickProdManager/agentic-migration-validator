#!/usr/bin/env python3
"""Run deterministic detection evals for fixture scenarios."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_ROOT = PROJECT_ROOT / "fixtures" / "scenarios"
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.diff_schema import diff_schema_for_scenario
from scripts.validate_scenario import validate_scenario
from tools.eval_runner import evaluate_findings
from tools.gatekeeper import GateContext, evaluate_cutover_readiness


FIXTURE_GATE_CONTEXT = GateContext(
    validation_completed=True,
    validation_accepted=True,
    final_runbook_published=True,
    approvals=("validation_acceptance", "cutover_recommendation", "ready"),
)


def main(argv: list[str]) -> int:
    scenario_ids = argv[1:] or default_scenario_ids()
    report = run_evals(scenario_ids)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


def run_evals(scenario_ids: list[str]) -> dict[str, Any]:
    scenario_results = []

    for scenario_id in scenario_ids:
        scenario = _load_scenario(scenario_id)
        _reset_scenario(scenario_id)
        validation_result = validate_scenario(scenario_id)
        schema_result = diff_schema_for_scenario(scenario_id)
        produced_findings = [
            *validation_result.get("findings", []),
            *schema_result.get("findings", []),
        ]
        expected_results = _load_json(PROJECT_ROOT / scenario["expected_results"])
        eval_result = evaluate_findings(
            expected_findings=expected_results.get("expected_findings", []),
            produced_findings=produced_findings,
            allowed_extra_findings=expected_results.get("allowed_extra_findings", []),
        )
        scenario_results.append(
            {
                "scenario_id": scenario_id,
                "model_calls": "disabled",
                "validation_findings": validation_result.get("findings", []),
                "schema_findings": schema_result.get("findings", []),
                "schema_data_check_results": schema_result.get("data_check_results", []),
                "gate_results": evaluate_cutover_readiness(
                    produced_findings,
                    FIXTURE_GATE_CONTEXT,
                ),
                **eval_result.to_dict(),
            }
        )

    report = {
        "model_calls": "disabled",
        "scenario_count": len(scenario_results),
        "passed": all(result["passed"] for result in scenario_results),
        "scenarios": scenario_results,
    }
    return report


def default_scenario_ids() -> list[str]:
    return sorted(path.parent.name for path in SCENARIOS_ROOT.glob("*/scenario.json"))


def _load_scenario(scenario_id: str) -> dict[str, Any]:
    path = SCENARIOS_ROOT / scenario_id / "scenario.json"
    if not path.exists():
        raise SystemExit(f"Unknown scenario: {scenario_id}")
    return _load_json(path)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _reset_scenario(scenario_id: str) -> None:
    env = {**os.environ, "QUIET": "1"}
    subprocess.run(
        ["sh", "scripts/reset_databases.sh", scenario_id],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
