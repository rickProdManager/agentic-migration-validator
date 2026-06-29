# Evidence References

Evidence references keep generated artifacts tied to real workflow outputs. They provide citation hygiene, not semantic proof. A resolved reference proves the cited object exists; deterministic gates still decide whether high-stakes claims are safe.

## Reference Types

| Prefix | Object |
| --- | --- |
| `tool.` | Output from a deterministic tool call. |
| `validation.` | Validation result emitted by the validation stage. |
| `finding.` | Structured finding. |
| `gate.` | Deterministic gatekeeper result. |
| `artifact.` | Accepted generated artifact. |
| `audit.` | Audit event. |
| `approval.` | Human approval event. |

## Format

References are stable strings scoped by stage, object type, object name, and version.

```text
tool.discovery.schema.public_orders.v1
validation.checksum.public_orders.v1
finding.validation.checksum_mismatch.public_orders.v1
audit.validation.run_2026_06_25_001.v1
approval.cutover.workspace_demo.v1
```

The MVP may store these as plain strings, but each reference must resolve to an object in the current workflow state or artifact store.

The local artifact writer emits `artifacts/evidence_registry.json`, which maps generated evidence refs to the artifact, scenario, stage, producer, and content hash that support them.

## Evidence Registry Entry

```json
{
  "evidence_ref": "validation.checksum.public_orders.v1",
  "workspace_id": "workspace_demo",
  "scenario_id": "failed_checksum",
  "source_type": "validation_result",
  "stage": "validation",
  "producer": "canonical_checksum",
  "created_at": "2026-06-25T12:00:00Z",
  "summary": "Checksum comparison for public.orders.",
  "uri": "artifacts/workspace_demo/failed_checksum/validation.json",
  "content_hash": "sha256:example"
}
```

## Validation Rules

- Every `evidence_ref` in an accepted artifact must resolve.
- Field-level claims that affect gates or risk scores require field-level evidence references.
- Narrative sections may use section-level evidence references when every claim in the section is covered by the same evidence.
- Missing, malformed, duplicate, or cross-workspace references are rejected.
- LLM-generated references are not trusted until resolved against the registry.
- Evidence references do not prove the cited output logically supports the claim. Reviewer critique can flag weak support, and deterministic gates protect high-stakes decisions.

## Artifact Claim Example

```json
{
  "claim_key": "orders_checksum_failed",
  "claim": "The target orders table differs from source despite matching row counts.",
  "claim_type": "validation_failure",
  "evidence_refs": [
    "validation.row_count.public_orders.v1",
    "validation.checksum.public_orders.v1"
  ]
}
```

## Unresolved Reference Finding

If an artifact includes an unresolved reference, the workflow emits a process-control finding:

```json
{
  "record_type": "gate_finding",
  "risk_axis": "process_control",
  "finding_key": "artifact.unresolved_evidence_reference:runbook:orders_checksum_failed",
  "finding_type": "artifact.unresolved_evidence_reference",
  "severity": "high",
  "status": "unresolved",
  "gate_effect": ["blocks_ready"],
  "evidence_refs": [],
  "summary": "Runbook claim orders_checksum_failed references missing evidence."
}
```
