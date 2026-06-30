# Initial API Contract

The MVP backend will expose a local API for scenario setup, workflow execution, approvals, artifacts, risk reports, and evals. This document is the initial contract; endpoint names may evolve as implementation expands.

The current implementation includes a local workflow response contract via `make run-workflow`, a dependency-free local JSON API via `make run-api`, and a local dashboard served from the same process with run history, launch controls, result summaries, approval inputs, and artifact/evidence/audit drilldowns. This is not the full FastAPI backend yet; it is the local surface the future backend can replace or wrap.

## Conventions

- Request and response bodies are JSON.
- IDs are stable strings, not database sequence numbers.
- Timestamps are ISO 8601 UTC strings.
- API handlers must return computed gate state, not stored gate overrides.
- Model-backed advisor stages must disclose when model calls were used.

## Core Resources

### Workspace

```json
{
  "workspace_id": "workspace_demo",
  "scenario_id": "failed_checksum",
  "status": "validation_blocked",
  "current_stage": "risk",
  "created_at": "2026-06-25T12:00:00Z",
  "updated_at": "2026-06-25T12:10:00Z"
}
```

### Workflow Stage

```json
{
  "stage": "validation",
  "status": "completed",
  "started_at": "2026-06-25T12:05:00Z",
  "completed_at": "2026-06-25T12:06:00Z",
  "model_calls": "disabled",
  "evidence_refs": ["validation.checksum.public_orders.v1"]
}
```

### Workflow Run

```json
{
  "workflow_run_id": "workflow.fixture_validation.20260629_120000",
  "workflow_version": "fixture_validation_workflow.v1",
  "workspace_id": "workspace_demo",
  "status": "completed",
  "current_stage": "artifacts_written",
  "model_calls": "disabled",
  "scenario_ids": ["clean_migration", "failed_checksum"],
  "started_at": "2026-06-29T12:00:00Z",
  "completed_at": "2026-06-29T12:01:00Z",
  "steps": [
    {
      "step": "run_deterministic_evals",
      "status": "completed",
      "model_calls": "disabled"
    },
    {
      "step": "generate_runbook_drafts",
      "status": "completed",
      "model_calls": "disabled"
    },
    {
      "step": "validate_artifact_bundle",
      "status": "completed",
      "model_calls": "disabled"
    },
    {
      "step": "write_artifact_bundle",
      "status": "completed",
      "model_calls": "disabled"
    }
  ],
  "artifact_refs": [
    "artifact.eval_report.fixture_suite.v1",
    "artifact.evidence_registry.fixture_suite.v1"
  ],
  "workflow_validation": {
    "passed": true,
    "issues": []
  }
}
```

### Artifact

```json
{
  "artifact_id": "artifact.risk_report.v1",
  "workspace_id": "workspace_demo",
  "artifact_type": "risk_report",
  "format": "json",
  "status": "accepted",
  "evidence_refs": ["finding.validation.checksum_mismatch.public_orders.v1"],
  "uri": "artifacts/workspace_demo/failed_checksum/risk_report.json"
}
```

## Endpoints

### `GET /health`

Returns service health and version.

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

Implemented by `make run-api`.

### `GET /scenarios`

Lists available fixture scenarios.

```json
{
  "scenarios": [
    {
      "scenario_id": "clean_migration",
      "description": "Baseline passing migration.",
      "primary_detector": "baseline_validation"
    }
  ]
}
```

Implemented by `make run-api`.

### `POST /workspaces`

Creates a workflow workspace for a scenario.

Request:

```json
{
  "scenario_id": "failed_checksum"
}
```

Response:

```json
{
  "workspace_id": "workspace_demo",
  "scenario_id": "failed_checksum",
  "status": "created",
  "current_stage": "not_started"
}
```

### `GET /workspaces/{workspace_id}`

Returns workflow state summary, including computed gates.

```json
{
  "workspace": {
    "workspace_id": "workspace_demo",
    "scenario_id": "failed_checksum",
    "status": "validation_blocked",
    "current_stage": "risk"
  },
  "stages": [],
  "risk": null,
  "gates": []
}
```

### `POST /workspaces/{workspace_id}/run`

Runs or resumes the workflow until the next blocking gate or completion.

Request:

```json
{
  "until_stage": "risk",
  "model_calls": "disabled"
}
```

Implemented local equivalents:

```sh
make run-workflow
make run-api
```

`make run-workflow` emits the workflow run shape above, includes the generated artifact manifest inline, snapshots referenced artifacts under `runs/`, and persists local run state. `make run-api` exposes this through `POST /workflows/run`, retrieval routes for run history, latest run state, workflow-scoped artifact/evidence lookup, audit logs, and a dashboard at `/` with workflow launch controls, result/progress/transition summaries, runbook, artifact, evidence, readiness, approval, and audit drilldowns.

Response:

```json
{
  "workspace_id": "workspace_demo",
  "status": "blocked",
  "current_stage": "validation",
  "blocking_gates": ["can_accept_validation"],
  "artifact_refs": ["artifact.validation_report.v1"]
}
```

### `POST /workflows/run`

Runs the local fixture workflow and returns the implemented workflow run response.

Optional query string:

```text
scenario_id=failed_checksum&scenario_id=schema_drift
```

Unknown `scenario_id` values are rejected before workflow execution.

Unknown scenario error:

```json
{
  "error": {
    "code": "unknown_scenario",
    "message": "Unknown scenario_id: missing_scenario"
  }
}
```

Runtime failure error:

```json
{
  "error": {
    "code": "workflow_run_failed",
    "message": "Workflow run failed. Confirm Docker fixture containers are running and retry.",
    "details": {
      "exception": "ConnectionError",
      "message": "database unavailable",
      "recovery_hint": "Run make db-up, then retry the workflow launch."
    }
  }
}
```

Response:

```json
{
  "workflow_run_id": "workflow.fixture_validation.20260629_120000",
  "workflow_version": "fixture_validation_workflow.v1",
  "workspace_id": "workspace_demo",
  "status": "completed",
  "current_stage": "artifacts_written",
  "stage_transitions": [
    {
      "from_stage": "not_started",
      "to_stage": "evaluation",
      "allowed": true,
      "unmet_prerequisites": []
    },
    {
      "from_stage": "evaluation",
      "to_stage": "runbook",
      "allowed": true,
      "unmet_prerequisites": []
    },
    {
      "from_stage": "runbook",
      "to_stage": "artifact_validation",
      "allowed": true,
      "unmet_prerequisites": []
    },
    {
      "from_stage": "artifact_validation",
      "to_stage": "artifacts_written",
      "allowed": true,
      "unmet_prerequisites": []
    }
  ],
  "workflow_validation": {
    "passed": true,
    "issues": []
  },
  "audit_event_count": 8,
  "audit_validation": {
    "passed": true,
    "issues": []
  },
  "artifact_manifest": {
    "passed": true,
    "artifact_count": 6
  },
  "run_state": {
    "passed": true,
    "workflow_run_id": "workflow.fixture_validation.20260629_120000",
    "audit_event_count": 8,
    "approval_count": 0
  }
}
```

Implemented by `make run-api`.

### `GET /workflows`

Returns persisted workflow run manifests, newest first.

Response:

```json
{
  "run_count": 1,
  "latest_workflow_run_id": "workflow.fixture_validation.20260629_120000",
  "runs": [
    {
      "run_store_version": "local_run_store.v1",
      "passed": true,
      "workflow_run_id": "workflow.fixture_validation.20260629_120000",
      "audit_event_count": 8,
      "approval_count": 0,
      "is_latest": true
    }
  ]
}
```

Implemented by `make run-api`.

### `GET /workflows/latest`

Returns the latest persisted workflow run and its local run manifest.

Response:

```json
{
  "run_manifest": {
    "run_store_version": "local_run_store.v1",
    "passed": true,
    "workflow_run_id": "workflow.fixture_validation.20260629_120000",
    "audit_event_count": 8,
    "approval_count": 0
  },
  "workflow_run": {
    "workflow_run_id": "workflow.fixture_validation.20260629_120000",
    "status": "completed",
    "current_stage": "artifacts_written"
  }
}
```

Implemented by `make run-api`.

### `GET /workflows/{workflow_run_id}`

Returns one persisted workflow run by id.

Response:

```json
{
  "workflow_run": {
    "workflow_run_id": "workflow.fixture_validation.20260629_120000",
    "status": "completed",
    "current_stage": "artifacts_written"
  }
}
```

Implemented by `make run-api`.

### `GET /workflows/{workflow_run_id}/artifacts/{artifact_id}`

Returns one generated artifact by ID using the selected workflow run's artifact manifest. This avoids mixing a historical run with the latest artifact bundle.

Response:

```json
{
  "artifact_id": "artifact.runbook_draft.failed_checksum.v1",
  "path": "runs/workflow.fixture_validation.20260629_120000/artifacts/scenarios/failed_checksum/runbook.json",
  "content_hash": "sha256:example",
  "metadata": {
    "artifact_type": "runbook",
    "scenario_id": "failed_checksum"
  },
  "content": {}
}
```

Implemented by `make run-api`.

### `GET /workflows/{workflow_run_id}/evidence/{evidence_ref}`

Resolves an evidence reference through the selected workflow run's evidence registry artifact.

Response:

```json
{
  "evidence_ref": "validation.checksum.public.customers.v1",
  "entry": {
    "source_artifact_id": "artifact.eval_report.fixture_suite.v1",
    "source_artifact_path": "eval_report.json",
    "content_hash": "sha256:example"
  }
}
```

Implemented by `make run-api`.

### `GET /workflows/{workflow_run_id}/audit`

Returns the persisted audit log for one workflow run.

Response:

```json
{
  "audit_schema_version": "audit_event.v1",
  "workflow_run_id": "workflow.fixture_validation.20260629_120000",
  "event_count": 8,
  "events": []
}
```

Implemented by `make run-api`.

### `GET /workflows/{workflow_run_id}/approvals`

Returns persisted approval records, effective approvals, and pending approval types for one workflow run.

Response:

```json
{
  "approval_schema_version": "approval_record.v1",
  "workflow_run_id": "workflow.fixture_validation.20260629_120000",
  "approval_count": 1,
  "effective_approvals": ["validation_acceptance"],
  "pending_approvals": [
    "cutover_recommendation",
    "final_planning",
    "ready",
    "rollback_recommendation"
  ],
  "approvals": []
}
```

Implemented by `make run-api`.

### `GET /workflows/{workflow_run_id}/readiness`

Returns approval-aware gate results for each scenario in a persisted workflow run. The view is derived from persisted approval records plus eval-report findings; it does not store or edit gate outputs.

Response:

```json
{
  "workflow_run_id": "workflow.fixture_validation.20260629_120000",
  "workspace_id": "workspace_demo",
  "status": "completed",
  "current_stage": "artifacts_written",
  "approval_state": {
    "approval_count": 1,
    "effective_approvals": ["validation_acceptance"],
    "pending_approvals": [
      "cutover_recommendation",
      "final_planning",
      "ready",
      "rollback_recommendation"
    ]
  },
  "scenario_count": 1,
  "scenarios": [
    {
      "scenario_id": "failed_checksum",
      "cutover_ready": false,
      "migration_ready": false,
      "blocked_gates": [
        "can_generate_final_plan",
        "can_recommend_cutover",
        "can_recommend_rollback",
        "can_mark_ready"
      ],
      "gate_results": {
        "can_accept_validation": {
          "gate": "can_accept_validation",
          "allowed": true,
          "blocking_findings": [],
          "missing_approvals": [],
          "unresolved_evidence_refs": [],
          "unmet_prerequisites": []
        },
        "can_recommend_cutover": {
          "gate": "can_recommend_cutover",
          "allowed": false,
          "blocking_findings": ["validation.checksum_mismatch:public.customers:*"],
          "missing_approvals": ["cutover_recommendation"],
          "unresolved_evidence_refs": [],
          "unmet_prerequisites": []
        }
      }
    }
  ]
}
```

Implemented by `make run-api`.

### `POST /workflows/{workflow_run_id}/approvals`

Submits a human approval decision for one workflow run. The approval is persisted under `runs/`, and an `approval_recorded` audit event is appended to that run's audit log.

Request:

```json
{
  "gate": "can_accept_validation",
  "decision": "approved",
  "actor": "human.reviewer",
  "notes": "Validation reviewed for demo.",
  "evidence_refs": ["artifact.eval_report.fixture_suite.v1"]
}
```

Response:

```json
{
  "approval": {
    "approval_id": "approval.validation_acceptance.workspace_demo.failed_checksum.v1",
    "approval_schema_version": "approval_record.v1",
    "workflow_run_id": "workflow.fixture_validation.20260629_120000",
    "workspace_id": "workspace_demo",
    "scenario_id": "failed_checksum",
    "gate": "can_accept_validation",
    "approval_type": "validation_acceptance",
    "actor": "human.reviewer",
    "decision": "approved",
    "status": "recorded",
    "evidence_refs": ["artifact.eval_report.fixture_suite.v1"]
  },
  "effective_approvals": ["validation_acceptance"],
  "pending_approvals": [
    "cutover_recommendation",
    "final_planning",
    "ready",
    "rollback_recommendation"
  ]
}
```

Implemented by `make run-api`.

### `GET /artifacts/latest-manifest`

Returns `artifacts/manifest.json` after a workflow or artifact run has produced it.

Response:

```json
{
  "passed": true,
  "artifact_count": 6,
  "artifacts": []
}
```

Implemented by `make run-api`.

### `GET /artifacts/{artifact_id}`

Returns one generated artifact by ID using the latest local artifact manifest.

Response:

```json
{
  "artifact_id": "artifact.runbook_draft.failed_checksum.v1",
  "path": "artifacts/scenarios/failed_checksum/runbook.json",
  "content_hash": "sha256:example",
  "metadata": {
    "artifact_type": "runbook",
    "scenario_id": "failed_checksum"
  },
  "content": {}
}
```

Implemented by `make run-api`.

### `GET /evidence/{evidence_ref}`

Resolves an evidence reference through `artifacts/evidence_registry.json`.

Response:

```json
{
  "evidence_ref": "validation.checksum.public.customers.v1",
  "entry": {
    "source_artifact_id": "artifact.eval_report.fixture_suite.v1",
    "source_artifact_path": "eval_report.json",
    "content_hash": "sha256:example"
  }
}
```

Implemented by `make run-api`.

### `GET /workspaces/{workspace_id}/findings`

Returns structured findings.

```json
{
  "findings": []
}
```

### `GET /workspaces/{workspace_id}/risk`

Returns the latest risk report.

```json
{
  "axes": {
    "migration_integrity": {
      "score": 75,
      "band": "critical",
      "raw_score": 60,
      "floor": 75
    }
  },
  "cutover_ready_risk_axes": ["migration_integrity", "process_control"]
}
```

### `GET /workspaces/{workspace_id}/artifacts/{artifact_id}`

Returns artifact metadata and content or a download URL.

### `GET /workspaces/{workspace_id}/audit`

Returns audit events for the workspace.

### `POST /evals/run`

Runs deterministic detection evals with model calls disabled.

Request:

```json
{
  "scenario_ids": ["clean_migration", "failed_checksum"],
  "model_calls": "disabled"
}
```

Response:

```json
{
  "eval_run_id": "eval.2026_06_25_001",
  "status": "completed",
  "report_artifact_id": "artifact.eval_report.v1"
}
```

## Error Shape

```json
{
  "error": {
    "code": "gate_blocked",
    "message": "Validation cannot be accepted until required approval is recorded.",
    "details": {
      "gate": "can_accept_validation",
      "missing_approvals": ["validation_acceptance"]
    }
  }
}
```
