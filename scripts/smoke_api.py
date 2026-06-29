#!/usr/bin/env python3
"""Smoke-test the local JSON API."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable


DEFAULT_BASE_URL = "http://127.0.0.1:8080"
MISSING_SCENARIO = "missing_scenario"


RequestJson = Callable[[str, str], tuple[int, dict[str, Any]]]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--workflow-scenario")
    args = parser.parse_args(argv[1:])

    result = run_smoke(
        args.base_url,
        workflow_scenario=args.workflow_scenario,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


def run_smoke(
    base_url: str,
    *,
    workflow_scenario: str | None = None,
    request_json: RequestJson | None = None,
) -> dict[str, Any]:
    request = request_json or _request_json
    base = base_url.rstrip("/")
    checks: list[dict[str, Any]] = []

    status, payload = request("GET", f"{base}/health")
    _add_check(
        checks,
        "health",
        status == 200 and payload.get("status") == "ok",
        {"status": status, "payload_status": payload.get("status")},
    )

    status, payload = request("GET", f"{base}/scenarios")
    scenarios = payload.get("scenarios", [])
    _add_check(
        checks,
        "scenarios",
        status == 200 and bool(scenarios),
        {"status": status, "scenario_count": len(scenarios) if isinstance(scenarios, list) else 0},
    )

    status, payload = request(
        "POST",
        f"{base}/workflows/run?scenario_id={urllib.parse.quote(MISSING_SCENARIO, safe='')}",
    )
    _add_check(
        checks,
        "unknown_scenario",
        status == 400 and payload.get("error", {}).get("code") == "unknown_scenario",
        {"status": status, "error_code": payload.get("error", {}).get("code")},
    )

    if workflow_scenario:
        _run_workflow_checks(base, workflow_scenario, request, checks)

    return {
        "base_url": base,
        "workflow_scenario": workflow_scenario,
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
    }


def _run_workflow_checks(
    base_url: str,
    workflow_scenario: str,
    request: RequestJson,
    checks: list[dict[str, Any]],
) -> None:
    scenario = urllib.parse.quote(workflow_scenario, safe="")
    status, payload = request("POST", f"{base_url}/workflows/run?scenario_id={scenario}")
    manifest = payload.get("artifact_manifest", {})
    _add_check(
        checks,
        "workflow_run",
        status == 200
        and payload.get("status") == "completed"
        and payload.get("workflow_validation", {}).get("passed") is True
        and manifest.get("passed") is True,
        {
            "status": status,
            "workflow_status": payload.get("status"),
            "artifact_count": manifest.get("artifact_count"),
        },
    )

    artifact_id = f"artifact.runbook_draft.{workflow_scenario}.v1"
    status, payload = request(
        "GET",
        f"{base_url}/artifacts/{urllib.parse.quote(artifact_id, safe='')}",
    )
    _add_check(
        checks,
        "artifact_retrieval",
        status == 200 and payload.get("artifact_id") == artifact_id,
        {"status": status, "artifact_id": payload.get("artifact_id")},
    )

    if workflow_scenario == "failed_checksum":
        evidence_ref = "validation.checksum.public.customers.v1"
        status, payload = request(
            "GET",
            f"{base_url}/evidence/{urllib.parse.quote(evidence_ref, safe='')}",
        )
        _add_check(
            checks,
            "evidence_retrieval",
            status == 200 and payload.get("evidence_ref") == evidence_ref,
            {
                "status": status,
                "evidence_ref": payload.get("evidence_ref"),
                "source_artifact_id": payload.get("entry", {}).get("source_artifact_id"),
            },
        )


def _request_json(method: str, url: str) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        url,
        data=b"" if method == "POST" else None,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def _add_check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    details: dict[str, Any],
) -> None:
    checks.append({"name": name, "passed": passed, **details})


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
