"""Human approval state helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from tools.audit import build_audit_event
from tools.gatekeeper import REQUIRED_APPROVAL_BY_GATE


APPROVAL_SCHEMA_VERSION = "approval_record.v1"
ALLOWED_DECISIONS = {"approved", "rejected", "revoked"}
REQUIRED_APPROVALS = tuple(sorted(set(REQUIRED_APPROVAL_BY_GATE.values())))
REQUIRED_FIELDS = (
    "approval_id",
    "approval_schema_version",
    "workflow_run_id",
    "workspace_id",
    "scenario_id",
    "gate",
    "approval_type",
    "actor",
    "decision",
    "status",
    "created_at",
    "evidence_refs",
    "audit_event_id",
)


@dataclass(frozen=True)
class ApprovalValidationIssue:
    path: str
    issue: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "issue": self.issue}


def build_approval_record(
    *,
    workflow_run_id: str,
    workspace_id: str,
    scenario_id: str,
    gate: str,
    actor: str,
    decision: str,
    evidence_refs: Iterable[str],
    created_at: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    if gate not in REQUIRED_APPROVAL_BY_GATE:
        raise ValueError(f"Unknown gate: {gate}")

    approval_type = REQUIRED_APPROVAL_BY_GATE[gate]
    created_at_value = created_at or _utc_now()
    approval_id = f"approval.{approval_type}.{workspace_id}.{scenario_id}.v1"
    audit_event_id = f"audit.{approval_id}.{decision}.{_compact_timestamp(created_at_value)}.v1"
    record = {
        "approval_id": approval_id,
        "approval_schema_version": APPROVAL_SCHEMA_VERSION,
        "workflow_run_id": workflow_run_id,
        "workspace_id": workspace_id,
        "scenario_id": scenario_id,
        "gate": gate,
        "approval_type": approval_type,
        "actor": actor,
        "decision": decision,
        "status": "recorded",
        "created_at": created_at_value,
        "evidence_refs": _dedupe(evidence_refs),
        "audit_event_id": audit_event_id,
    }
    if notes:
        record["notes"] = notes
    return record


def validate_approval_record(
    record: Mapping[str, Any],
) -> tuple[ApprovalValidationIssue, ...]:
    issues: list[ApprovalValidationIssue] = []
    for field in REQUIRED_FIELDS:
        if field not in record:
            issues.append(ApprovalValidationIssue(field, "missing_field"))

    for field in (
        "approval_id",
        "workflow_run_id",
        "workspace_id",
        "scenario_id",
        "actor",
        "created_at",
    ):
        if field in record and (not isinstance(record.get(field), str) or not record.get(field)):
            issues.append(ApprovalValidationIssue(field, "invalid_string"))

    if record.get("approval_schema_version") != APPROVAL_SCHEMA_VERSION:
        issues.append(ApprovalValidationIssue("approval_schema_version", "invalid_schema_version"))

    gate = record.get("gate")
    approval_type = record.get("approval_type")
    if gate not in REQUIRED_APPROVAL_BY_GATE:
        issues.append(ApprovalValidationIssue("gate", "invalid_gate"))
    elif approval_type != REQUIRED_APPROVAL_BY_GATE[gate]:
        issues.append(ApprovalValidationIssue("approval_type", "gate_approval_mismatch"))

    if record.get("decision") not in ALLOWED_DECISIONS:
        issues.append(ApprovalValidationIssue("decision", "invalid_decision"))
    if record.get("status") != "recorded":
        issues.append(ApprovalValidationIssue("status", "invalid_status"))
    if not _is_string_list(record.get("evidence_refs")):
        issues.append(ApprovalValidationIssue("evidence_refs", "invalid_evidence_refs"))
    if record.get("decision") == "approved" and not record.get("evidence_refs"):
        issues.append(ApprovalValidationIssue("evidence_refs", "missing_approval_evidence"))

    audit_event_id = record.get("audit_event_id")
    if not isinstance(audit_event_id, str) or not audit_event_id.startswith("audit."):
        issues.append(ApprovalValidationIssue("audit_event_id", "invalid_audit_event_id"))

    return tuple(issues)


def effective_approvals(
    records: Iterable[Mapping[str, Any]],
) -> tuple[str, ...]:
    latest_by_type: dict[str, Mapping[str, Any]] = {}
    valid_records = [
        record
        for record in records
        if not validate_approval_record(record)
    ]
    for record in sorted(valid_records, key=lambda item: str(item.get("created_at"))):
        latest_by_type[str(record["approval_type"])] = record

    return tuple(
        sorted(
            approval_type
            for approval_type, record in latest_by_type.items()
            if record.get("decision") == "approved"
        )
    )


def pending_approvals(
    records: Iterable[Mapping[str, Any]],
    *,
    required_approvals: Iterable[str] = REQUIRED_APPROVALS,
) -> tuple[str, ...]:
    effective = set(effective_approvals(records))
    return tuple(
        sorted(
            approval
            for approval in required_approvals
            if approval not in effective
        )
    )


def build_approval_audit_event(record: Mapping[str, Any]) -> dict[str, Any]:
    return build_audit_event(
        audit_event_id=str(record["audit_event_id"]),
        workflow_run_id=str(record["workflow_run_id"]),
        workspace_id=str(record["workspace_id"]),
        scenario_id=str(record["scenario_id"]),
        actor_name=str(record["actor"]),
        actor_type="human",
        stage="approval",
        decision="approval_recorded",
        status="recorded",
        evidence_refs=record.get("evidence_refs", []),
        approval_id=str(record["approval_id"]),
        created_at=str(record["created_at"]),
        metadata={
            "gate": record.get("gate"),
            "approval_type": record.get("approval_type"),
            "approval_decision": record.get("decision"),
        },
    )


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


def _compact_timestamp(value: str) -> str:
    return (
        value.replace("-", "")
        .replace(":", "")
        .replace(".", "")
        .replace("Z", "")
        .replace("T", "_")
    )
