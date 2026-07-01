"""Audit event schema helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


AUDIT_SCHEMA_VERSION = "audit_event.v1"
REQUIRED_FIELDS = (
    "audit_event_id",
    "audit_schema_version",
    "workflow_run_id",
    "workspace_id",
    "scenario_id",
    "created_at",
    "actor_name",
    "actor_type",
    "stage",
    "decision",
    "status",
    "evidence_refs",
    "finding_keys",
    "artifact_ids",
)
ALLOWED_ACTOR_TYPES = {"system", "tool", "advisor", "human"}
ALLOWED_DECISIONS = {
    "stage_started",
    "stage_completed",
    "tool_called",
    "finding_emitted",
    "artifact_generated",
    "artifact_rejected",
    "artifact_accepted",
    "approval_recorded",
    "gate_allowed",
    "gate_blocked",
    "transition_allowed",
    "transition_blocked",
    "state_edited",
}
ALLOWED_STATUSES = {
    "started",
    "completed",
    "failed",
    "blocked",
    "accepted",
    "rejected",
    "recorded",
}
ARTIFACT_DECISIONS = {
    "artifact_generated",
    "artifact_rejected",
    "artifact_accepted",
}
GATE_DECISIONS = {"gate_allowed", "gate_blocked"}
TRANSITION_DECISIONS = {"transition_allowed", "transition_blocked"}


@dataclass(frozen=True)
class AuditValidationIssue:
    path: str
    issue: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "issue": self.issue}


def build_audit_event(
    *,
    audit_event_id: str,
    workflow_run_id: str,
    workspace_id: str,
    scenario_id: str,
    actor_name: str,
    actor_type: str,
    stage: str,
    decision: str,
    status: str,
    evidence_refs: Iterable[str] = (),
    finding_keys: Iterable[str] = (),
    artifact_ids: Iterable[str] = (),
    created_at: str | None = None,
    tool_name: str | None = None,
    input_summary: str | None = None,
    output_summary: str | None = None,
    gate: str | None = None,
    approval_id: str | None = None,
    from_stage: str | None = None,
    to_stage: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    error_type: str | None = None,
    retryable: bool | None = None,
    severity: str | None = None,
    confidence_basis: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    event = {
        "audit_event_id": audit_event_id,
        "audit_schema_version": AUDIT_SCHEMA_VERSION,
        "workflow_run_id": workflow_run_id,
        "workspace_id": workspace_id,
        "scenario_id": scenario_id,
        "created_at": created_at or _utc_now(),
        "actor_name": actor_name,
        "actor_type": actor_type,
        "stage": stage,
        "decision": decision,
        "status": status,
        "evidence_refs": _dedupe(evidence_refs),
        "finding_keys": _dedupe(finding_keys),
        "artifact_ids": _dedupe(artifact_ids),
    }
    optional_fields = {
        "tool_name": tool_name,
        "input_summary": input_summary,
        "output_summary": output_summary,
        "gate": gate,
        "approval_id": approval_id,
        "from_stage": from_stage,
        "to_stage": to_stage,
        "error_code": error_code,
        "error_message": error_message,
        "error_type": error_type,
        "retryable": retryable,
        "severity": severity,
        "confidence_basis": confidence_basis,
        "metadata": dict(metadata) if metadata is not None else None,
    }
    event.update(
        {
            key: value
            for key, value in optional_fields.items()
            if value is not None
        }
    )
    return event


def validate_audit_event(
    event: Mapping[str, Any],
) -> tuple[AuditValidationIssue, ...]:
    issues: list[AuditValidationIssue] = []

    for field in REQUIRED_FIELDS:
        if field not in event:
            issues.append(AuditValidationIssue(field, "missing_field"))

    if event.get("audit_schema_version") != AUDIT_SCHEMA_VERSION:
        issues.append(AuditValidationIssue("audit_schema_version", "invalid_schema_version"))
    if event.get("actor_type") not in ALLOWED_ACTOR_TYPES:
        issues.append(AuditValidationIssue("actor_type", "invalid_actor_type"))
    if event.get("decision") not in ALLOWED_DECISIONS:
        issues.append(AuditValidationIssue("decision", "invalid_decision"))
    if event.get("status") not in ALLOWED_STATUSES:
        issues.append(AuditValidationIssue("status", "invalid_status"))

    for field in ("evidence_refs", "finding_keys", "artifact_ids"):
        if not _is_string_list(event.get(field)):
            issues.append(AuditValidationIssue(field, "invalid_link_list"))

    decision = event.get("decision")
    if decision == "finding_emitted":
        if not event.get("finding_keys"):
            issues.append(AuditValidationIssue("finding_keys", "missing_finding_link"))
        if not event.get("evidence_refs"):
            issues.append(AuditValidationIssue("evidence_refs", "missing_evidence_link"))

    if decision in ARTIFACT_DECISIONS and not event.get("artifact_ids"):
        issues.append(AuditValidationIssue("artifact_ids", "missing_artifact_link"))

    if decision in GATE_DECISIONS and not event.get("gate"):
        issues.append(AuditValidationIssue("gate", "missing_gate"))

    if decision in TRANSITION_DECISIONS:
        if not event.get("from_stage"):
            issues.append(AuditValidationIssue("from_stage", "missing_from_stage"))
        if not event.get("to_stage"):
            issues.append(AuditValidationIssue("to_stage", "missing_to_stage"))

    if decision == "approval_recorded":
        if not event.get("approval_id"):
            issues.append(AuditValidationIssue("approval_id", "missing_approval_id"))
        if not event.get("gate"):
            issues.append(AuditValidationIssue("gate", "missing_gate"))

    if event.get("confidence_basis") and not event.get("evidence_refs"):
        issues.append(AuditValidationIssue("confidence_basis", "missing_evidence_link"))

    if event.get("status") == "failed":
        if not event.get("error_code"):
            issues.append(AuditValidationIssue("error_code", "missing_error_code"))
        if not event.get("error_message"):
            issues.append(AuditValidationIssue("error_message", "missing_error_message"))

    for field in (
        "audit_event_id",
        "workflow_run_id",
        "workspace_id",
        "scenario_id",
        "created_at",
        "actor_name",
        "actor_type",
        "stage",
        "decision",
        "status",
        "gate",
        "approval_id",
        "from_stage",
        "to_stage",
        "error_code",
        "error_message",
        "error_type",
    ):
        if field in event and (not isinstance(event.get(field), str) or not event.get(field)):
            issues.append(AuditValidationIssue(field, "invalid_string"))

    if "retryable" in event and not isinstance(event.get("retryable"), bool):
        issues.append(AuditValidationIssue("retryable", "invalid_boolean"))

    return tuple(issues)


def validate_audit_log(
    events: Iterable[Mapping[str, Any]],
) -> tuple[AuditValidationIssue, ...]:
    issues: list[AuditValidationIssue] = []
    seen_ids: set[str] = set()
    for index, event in enumerate(events):
        event_id = event.get("audit_event_id")
        if isinstance(event_id, str):
            if event_id in seen_ids:
                issues.append(
                    AuditValidationIssue(
                        f"events.{index}.audit_event_id",
                        "duplicate_audit_event_id",
                    )
                )
            seen_ids.add(event_id)

        for issue in validate_audit_event(event):
            issues.append(
                AuditValidationIssue(
                    path=f"events.{index}.{issue.path}",
                    issue=issue.issue,
                )
            )
    return tuple(issues)


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


def _dedupe(values: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
