# Audit Events

Every workflow stage, advisor, tool action, approval, and human state edit emits a structured audit event. Audit events are evidence-bearing records, not free-form logs: each event must identify the workflow run it belongs to and the artifacts, findings, evidence refs, gates, or approvals it concerns.

The executable contract lives in `tools/audit.py`.

## Required Fields

```json
{
  "audit_event_id": "audit.validation.checksum.public_customers.v1",
  "audit_schema_version": "audit_event.v1",
  "workflow_run_id": "workflow.fixture_validation.20260630_120000",
  "workspace_id": "workspace_demo",
  "scenario_id": "failed_checksum",
  "created_at": "2026-06-30T12:00:00Z",
  "actor_name": "checksum_validation",
  "actor_type": "tool",
  "stage": "validation",
  "decision": "finding_emitted",
  "status": "completed",
  "evidence_refs": ["validation.checksum.public.customers.v1"],
  "finding_keys": ["validation.checksum_mismatch:public.customers:*"],
  "artifact_ids": []
}
```

## Optional Fields

```json
{
  "tool_name": "checksum.compare_table",
  "input_summary": "Compared source and target public.customers checksums.",
  "output_summary": "Checksum mismatch detected for public.customers.",
  "gate": "can_mark_ready",
  "approval_id": "approval.ready.workspace_demo.failed_checksum.v1",
  "from_stage": "runbook",
  "to_stage": "artifact_validation",
  "error_code": "workflow_step_failed:validate_artifact_bundle",
  "error_message": "Workflow step validate_artifact_bundle failed.",
  "error_type": "workflow_step_failure",
  "retryable": true,
  "severity": "high",
  "confidence_basis": "Exact full-table checksum over all rows.",
  "metadata": {
    "table": "public.customers"
  }
}
```

## Actor Types

- `system`
- `tool`
- `advisor`
- `human`

## Decisions

- `stage_started`
- `stage_completed`
- `tool_called`
- `finding_emitted`
- `artifact_generated`
- `artifact_rejected`
- `artifact_accepted`
- `approval_recorded`
- `gate_allowed`
- `gate_blocked`
- `transition_allowed`
- `transition_blocked`
- `state_edited`

## Statuses

- `started`
- `completed`
- `failed`
- `blocked`
- `accepted`
- `rejected`
- `recorded`

## Linkage Rules

- `finding_emitted` requires at least one `finding_key` and one `evidence_ref`.
- `artifact_generated`, `artifact_rejected`, and `artifact_accepted` require at least one `artifact_id`.
- `gate_allowed` and `gate_blocked` require `gate`.
- `approval_recorded` requires `approval_id` and `gate`.
- `transition_allowed` and `transition_blocked` require `from_stage` and `to_stage`.
- Any event with `status=failed` requires `error_code` and `error_message`.
- `confidence_basis` requires supporting `evidence_refs`.
- `audit_event_id` values must be unique within an audit log.
- `retryable`, when present, must be boolean.

## Logging Rules

- Audit event ids must be stable enough to reference from artifacts.
- Tool events should include summarized inputs and outputs, not secrets.
- Database connection strings must never appear in audit logs.
- Human edits to workflow state must be logged.
- Gate outputs should be logged as computed events, not stored as editable state.
- `confidence_basis` is allowed only when derived from deterministic evidence such as sample size, rule severity, or validation coverage.
- Error fields should be structured and sanitized. Use stable `error_code` values for programmatic grouping, concise `error_message` text for operators, and avoid stack traces, connection strings, credentials, host paths, or raw exception payloads in audit events.
