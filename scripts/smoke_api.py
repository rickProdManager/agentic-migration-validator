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


RequestJson = Callable[[str, str, dict[str, Any] | None], tuple[int, dict[str, Any]]]


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

    status, payload = request("GET", f"{base}/health", None)
    _add_check(
        checks,
        "health",
        status == 200 and payload.get("status") == "ok",
        {"status": status, "payload_status": payload.get("status")},
    )

    status, payload = request("GET", f"{base}/scenarios", None)
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
        None,
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
    status, payload = request("POST", f"{base_url}/workflows/run?scenario_id={scenario}", None)
    manifest = payload.get("artifact_manifest", {})
    workflow_run_id = payload.get("workflow_run_id")
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

    status, payload = request("GET", f"{base_url}/workflows/latest", None)
    _add_check(
        checks,
        "workflow_latest",
        status == 200
        and payload.get("run_manifest", {}).get("workflow_run_id") == workflow_run_id,
        {
            "status": status,
            "workflow_run_id": payload.get("run_manifest", {}).get("workflow_run_id"),
        },
    )

    status, payload = request("GET", f"{base_url}/workflows", None)
    _add_check(
        checks,
        "workflow_runs",
        status == 200
        and payload.get("run_count", 0) > 0
        and any(
            run.get("workflow_run_id") == workflow_run_id
            for run in payload.get("runs", [])
        ),
        {
            "status": status,
            "run_count": payload.get("run_count"),
            "latest_workflow_run_id": payload.get("latest_workflow_run_id"),
        },
    )

    audit_path = urllib.parse.quote(str(workflow_run_id), safe="")
    status, payload = request("GET", f"{base_url}/workflows/{audit_path}/audit", None)
    _add_check(
        checks,
        "workflow_audit",
        status == 200
        and payload.get("workflow_run_id") == workflow_run_id
        and payload.get("event_count", 0) > 0,
        {
            "status": status,
            "workflow_run_id": payload.get("workflow_run_id"),
            "event_count": payload.get("event_count"),
        },
    )

    artifact_id = f"artifact.runbook_draft.{workflow_scenario}.v1"
    status, payload = request(
        "GET",
        f"{base_url}/workflows/{audit_path}/artifacts/{urllib.parse.quote(artifact_id, safe='')}",
        None,
    )
    _add_check(
        checks,
        "artifact_retrieval",
        status == 200 and payload.get("artifact_id") == artifact_id,
        {"status": status, "artifact_id": payload.get("artifact_id")},
    )

    approval_url = f"{base_url}/workflows/{audit_path}/approvals"
    status, payload = request(
        "POST",
        approval_url,
        {
            "gate": "can_accept_validation",
            "actor": "human.reviewer",
            "decision": "approved",
            "evidence_refs": ["artifact.eval_report.fixture_suite.v1"],
            "notes": "Smoke test approval.",
        },
    )
    _add_check(
        checks,
        "approval_submission",
        status == 201
        and payload.get("approval", {}).get("approval_type") == "validation_acceptance"
        and "validation_acceptance" in payload.get("effective_approvals", []),
        {
            "status": status,
            "approval_type": payload.get("approval", {}).get("approval_type"),
        },
    )

    status, payload = request("GET", approval_url, None)
    _add_check(
        checks,
        "approval_retrieval",
        status == 200
        and payload.get("approval_count") == 1
        and "validation_acceptance" in payload.get("effective_approvals", []),
        {
            "status": status,
            "approval_count": payload.get("approval_count"),
        },
    )

    status, payload = request("GET", f"{base_url}/workflows/{audit_path}/readiness", None)
    scenario_results = payload.get("scenarios", [])
    first_scenario = scenario_results[0] if scenario_results else {}
    gate_results = first_scenario.get("gate_results", {})
    _add_check(
        checks,
        "approval_aware_readiness",
        status == 200
        and "validation_acceptance" in payload.get("approval_state", {}).get("effective_approvals", [])
        and gate_results.get("can_accept_validation", {}).get("allowed") is True,
        {
            "status": status,
            "scenario_count": payload.get("scenario_count"),
            "can_accept_validation": gate_results.get("can_accept_validation", {}).get("allowed"),
            "can_recommend_cutover": gate_results.get("can_recommend_cutover", {}).get("allowed"),
        },
    )

    if workflow_scenario == "failed_checksum":
        evidence_ref = "validation.checksum.public.customers.v1"
        status, payload = request(
            "GET",
            f"{base_url}/workflows/{audit_path}/evidence/{urllib.parse.quote(evidence_ref, safe='')}",
            None,
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


def _request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    data = None
    headers = {}
    if method == "POST":
        data = json.dumps(payload).encode("utf-8") if payload is not None else b""
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
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
