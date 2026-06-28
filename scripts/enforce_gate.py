#!/usr/bin/env python3
"""Enforce a deterministic gate for one fixture scenario."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.diff_schema import diff_schema_for_scenario
from scripts.validate_scenario import validate_scenario
from tools.gatekeeper import GateBlockedError, GateContext, require_gate_allowed


FIXTURE_GATE_CONTEXT = GateContext(
    validation_completed=True,
    validation_accepted=True,
    final_runbook_published=True,
    approvals=("validation_acceptance", "cutover_recommendation", "ready"),
)


def main(argv: list[str]) -> int:
    scenario_id = argv[1] if len(argv) > 1 else "clean_migration"
    gate = argv[2] if len(argv) > 2 else "can_mark_ready"
    report = enforce_scenario_gate(scenario_id, gate)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["allowed"] else 1


def enforce_scenario_gate(scenario_id: str, gate: str) -> dict[str, Any]:
    schema_result = diff_schema_for_scenario(scenario_id)
    validation_result = validate_scenario(scenario_id)
    produced_findings = [
        *validation_result.get("findings", []),
        *schema_result.get("findings", []),
    ]

    try:
        result = require_gate_allowed(gate, produced_findings, FIXTURE_GATE_CONTEXT)
    except GateBlockedError as error:
        result = error.result

    return {
        "scenario_id": scenario_id,
        "model_calls": "disabled",
        **result.to_dict(),
    }


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
