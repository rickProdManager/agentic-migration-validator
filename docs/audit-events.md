# Audit Events

Every workflow stage, advisor, tool action, approval, and human state edit should emit a structured audit event.

## Required Fields

```json
{
  "audit_event_id": "audit.validation.checksum.public_orders.v1",
  "timestamp": "2026-06-25T12:00:00Z",
  "workspace_id": "workspace_demo",
  "scenario_id": "failed_checksum",
  "actor_name": "canonical_checksum",
  "actor_type": "tool",
  "stage": "validation",
  "tool_name": "checksum.compare_table",
  "input_summary": "Compared source and target public.orders canonical checksums.",
  "output_summary": "Checksum mismatch detected for public.orders.",
  "evidence_refs": ["validation.checksum.public_orders.v1"],
  "decision": "finding_emitted",
  "severity": "high",
  "confidence_basis": "Exact full-table checksum over 1200 rows.",
  "approval_status": null
}
```

## Actor Types

- `system`
- `tool`
- `advisor`
- `human`

## Decisions

Initial decision values:

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
- `state_edited`

## Rules

- Audit event ids must be stable enough to reference from artifacts.
- Tool events should include summarized inputs and outputs, not secrets.
- Database connection strings must never appear in audit logs.
- Human edits to workflow state must be logged.
- Gate outputs should be logged as computed events, not stored as editable state.
- `confidence_basis` is allowed only when derived from deterministic evidence such as sample size, rule severity, or validation coverage.

