#!/usr/bin/env python3
"""Generate an evidence-bound runbook draft for one scenario."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.diff_schema import diff_schema_for_scenario
from scripts.run_eval import FIXTURE_GATE_CONTEXT
from scripts.validate_scenario import validate_scenario
from tools.gatekeeper import evaluate_cutover_readiness
from tools.live_model import generate_openai_text, live_model_config_from_env
from tools.runbook_advisor import build_live_model_prompt, generate_runbook_draft


def main(argv: list[str]) -> int:
    scenario_id = argv[1] if len(argv) > 1 else "clean_migration"
    runbook = generate_scenario_runbook(scenario_id)
    print(json.dumps(runbook, indent=2, sort_keys=True))
    return 0 if runbook["boundary_validation"]["passed"] else 1


def generate_scenario_runbook(scenario_id: str) -> dict:
    schema_result = diff_schema_for_scenario(scenario_id)
    validation_result = validate_scenario(scenario_id)
    findings = [
        *validation_result.get("findings", []),
        *schema_result.get("findings", []),
    ]
    gate_results = evaluate_cutover_readiness(findings, FIXTURE_GATE_CONTEXT)
    runbook = generate_runbook_draft(
        scenario_id=scenario_id,
        validation_findings=validation_result.get("findings", []),
        schema_findings=schema_result.get("findings", []),
        schema_data_check_results=schema_result.get("data_check_results", []),
        gate_results=gate_results,
    )
    if os.environ.get("RUNBOOK_MODEL_CALLS") != "enabled":
        return runbook

    model_narrative = generate_openai_text(
        prompt=build_live_model_prompt(runbook),
        config=live_model_config_from_env(),
    )
    return generate_runbook_draft(
        scenario_id=scenario_id,
        validation_findings=validation_result.get("findings", []),
        schema_findings=schema_result.get("findings", []),
        schema_data_check_results=schema_result.get("data_check_results", []),
        gate_results=gate_results,
        model_narrative=model_narrative,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
