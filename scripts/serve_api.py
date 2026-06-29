#!/usr/bin/env python3
"""Serve the local workflow API with the Python standard library."""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_eval import default_scenario_ids
from scripts.run_workflow import run_fixture_workflow
from tools.api import error_response, health_response, latest_manifest_response, scenarios_response


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080


class WorkflowApiHandler(BaseHTTPRequestHandler):
    server_version = "AgenticMigrationValidator/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
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
            self._write_json(200, run_fixture_workflow(list(scenario_ids)))
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
