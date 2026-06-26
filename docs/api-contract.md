# Initial API Contract

The MVP backend will expose a local API for scenario setup, workflow execution, approvals, artifacts, risk reports, and evals. This document is the Day 1 contract; endpoint names may evolve once implementation begins.

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

### `POST /workspaces/{workspace_id}/approvals`

Submits a human approval decision.

Request:

```json
{
  "gate": "validation_acceptance",
  "decision": "approved",
  "actor": "human.reviewer",
  "notes": "Validation reviewed for demo.",
  "evidence_refs": ["artifact.validation_report.v1"]
}
```

Response:

```json
{
  "approval_id": "approval.validation_acceptance.workspace_demo.v1",
  "status": "recorded"
}
```

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

