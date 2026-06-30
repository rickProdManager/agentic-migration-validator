#!/usr/bin/env python3
"""Serve the local workflow API with the Python standard library."""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
UI_ROOT = PROJECT_ROOT / "ui"

from scripts.run_eval import default_scenario_ids
from scripts.run_workflow import run_fixture_workflow
from tools.api import (
    artifact_response,
    error_response,
    evidence_response,
    health_response,
    latest_manifest_response,
    latest_workflow_run_response,
    scenarios_response,
    submit_workflow_approval_response,
    validate_requested_scenarios,
    workflow_run_failed_response,
    workflow_audit_response,
    workflow_approvals_response,
    workflow_artifact_response,
    workflow_evidence_response,
    workflow_run_response,
    workflow_runs_response,
    workflow_readiness_response,
)


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080


class WorkflowApiHandler(BaseHTTPRequestHandler):
    server_version = "AgenticMigrationValidator/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/ui", "/ui/"}:
            self._write_static(UI_ROOT / "index.html")
            return
        if parsed.path.startswith("/ui/"):
            static_path = (UI_ROOT / unquote(parsed.path.removeprefix("/ui/"))).resolve()
            if not _is_relative_to(static_path, UI_ROOT.resolve()):
                status, payload = error_response(
                    "not_found",
                    f"No route for GET {parsed.path}",
                    status=404,
                )
                self._write_json(status, payload)
                return
            self._write_static(static_path)
            return
        if parsed.path == "/health":
            self._write_json(200, health_response())
            return
        if parsed.path == "/scenarios":
            self._write_json(200, scenarios_response(PROJECT_ROOT))
            return
        if parsed.path == "/artifacts/latest-manifest":
            status, payload = latest_manifest_response(PROJECT_ROOT)
            self._write_json(status, payload)
            return
        if parsed.path.startswith("/artifacts/"):
            artifact_id = unquote(parsed.path.removeprefix("/artifacts/"))
            status, payload = artifact_response(PROJECT_ROOT, artifact_id)
            self._write_json(status, payload)
            return
        if parsed.path.startswith("/evidence/"):
            evidence_ref = unquote(parsed.path.removeprefix("/evidence/"))
            status, payload = evidence_response(PROJECT_ROOT, evidence_ref)
            self._write_json(status, payload)
            return
        if parsed.path == "/workflows":
            status, payload = workflow_runs_response(PROJECT_ROOT)
            self._write_json(status, payload)
            return
        if parsed.path == "/workflows/latest":
            status, payload = latest_workflow_run_response(PROJECT_ROOT)
            self._write_json(status, payload)
            return
        if parsed.path.startswith("/workflows/") and "/artifacts/" in parsed.path:
            workflow_run_id, artifact_id = _split_nested_workflow_route(
                parsed.path,
                "artifacts",
            )
            status, payload = workflow_artifact_response(
                PROJECT_ROOT,
                unquote(workflow_run_id),
                unquote(artifact_id),
            )
            self._write_json(status, payload)
            return
        if parsed.path.startswith("/workflows/") and "/evidence/" in parsed.path:
            workflow_run_id, evidence_ref = _split_nested_workflow_route(
                parsed.path,
                "evidence",
            )
            status, payload = workflow_evidence_response(
                PROJECT_ROOT,
                unquote(workflow_run_id),
                unquote(evidence_ref),
            )
            self._write_json(status, payload)
            return
        if parsed.path.startswith("/workflows/") and parsed.path.endswith("/audit"):
            workflow_run_id = unquote(parsed.path.removeprefix("/workflows/").removesuffix("/audit"))
            status, payload = workflow_audit_response(PROJECT_ROOT, workflow_run_id)
            self._write_json(status, payload)
            return
        if parsed.path.startswith("/workflows/") and parsed.path.endswith("/approvals"):
            workflow_run_id = unquote(
                parsed.path.removeprefix("/workflows/").removesuffix("/approvals")
            )
            status, payload = workflow_approvals_response(PROJECT_ROOT, workflow_run_id)
            self._write_json(status, payload)
            return
        if parsed.path.startswith("/workflows/") and parsed.path.endswith("/readiness"):
            workflow_run_id = unquote(
                parsed.path.removeprefix("/workflows/").removesuffix("/readiness")
            )
            status, payload = workflow_readiness_response(PROJECT_ROOT, workflow_run_id)
            self._write_json(status, payload)
            return
        if parsed.path.startswith("/workflows/"):
            workflow_run_id = unquote(parsed.path.removeprefix("/workflows/"))
            status, payload = workflow_run_response(PROJECT_ROOT, workflow_run_id)
            self._write_json(status, payload)
            return

        status, payload = error_response(
            "not_found",
            f"No route for GET {parsed.path}",
            status=404,
        )
        self._write_json(status, payload)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/workflows/run":
            query = parse_qs(parsed.query)
            scenario_ids = query.get("scenario_id") or default_scenario_ids()
            validation_error = validate_requested_scenarios(PROJECT_ROOT, list(scenario_ids))
            if validation_error is not None:
                status, payload = validation_error
                self._write_json(status, payload)
                return
            try:
                self._write_json(200, run_fixture_workflow(list(scenario_ids)))
            except Exception as error:
                status, payload = workflow_run_failed_response(error)
                self._write_json(status, payload)
            return
        if parsed.path.startswith("/workflows/") and parsed.path.endswith("/approvals"):
            workflow_run_id = unquote(
                parsed.path.removeprefix("/workflows/").removesuffix("/approvals")
            )
            status, body = self._read_json_body()
            if status != 200:
                self._write_json(status, body)
                return
            status, payload = submit_workflow_approval_response(
                PROJECT_ROOT,
                workflow_run_id,
                body,
            )
            self._write_json(status, payload)
            return

        status, payload = error_response(
            "not_found",
            f"No route for POST {parsed.path}",
            status=404,
        )
        self._write_json(status, payload)

    def log_message(self, format: str, *args) -> None:
        return

    def _write_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_static(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            status, payload = error_response(
                "not_found",
                "Static asset not found.",
                status=404,
            )
            self._write_json(status, payload)
            return

        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", _content_type(path))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> tuple[int, dict]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return 400, error_response(
                "invalid_json",
                "Request body must be a JSON object.",
                status=400,
            )[1]

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            return 400, error_response(
                "invalid_json",
                "Request body must be valid JSON.",
                status=400,
            )[1]

        if not isinstance(payload, dict):
            return 400, error_response(
                "invalid_json",
                "Request body must be a JSON object.",
                status=400,
            )[1]
        return 200, payload


def _content_type(path: Path) -> str:
    if path.suffix == ".html":
        return "text/html; charset=utf-8"
    if path.suffix == ".css":
        return "text/css; charset=utf-8"
    if path.suffix == ".js":
        return "application/javascript; charset=utf-8"
    return "application/octet-stream"


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _split_nested_workflow_route(path: str, segment: str) -> tuple[str, str]:
    route = path.removeprefix("/workflows/")
    workflow_run_id, nested = route.split(f"/{segment}/", 1)
    return workflow_run_id, nested


def main(argv: list[str]) -> int:
    host = argv[1] if len(argv) > 1 else DEFAULT_HOST
    port = int(argv[2]) if len(argv) > 2 else DEFAULT_PORT
    server = ThreadingHTTPServer((host, port), WorkflowApiHandler)
    print(f"Serving Agentic Migration Validator API on http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
