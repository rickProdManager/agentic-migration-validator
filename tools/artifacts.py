"""Artifact metadata, hashing, and validation helpers."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REQUIRED_METADATA_FIELDS = (
    "artifact_id",
    "workspace_id",
    "scenario_id",
    "artifact_type",
    "format",
    "status",
    "created_at",
    "producer",
    "model_calls",
    "evidence_refs",
    "content_hash",
)
ALLOWED_STATUSES = {"draft", "rejected", "accepted", "published"}
ALLOWED_MODEL_CALLS = {"disabled", "enabled"}


@dataclass(frozen=True)
class ArtifactValidationIssue:
    path: str
    issue: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "issue": self.issue}


def build_artifact(
    payload: Mapping[str, Any],
    *,
    artifact_id: str,
    artifact_type: str,
    scenario_id: str,
    producer: str,
    model_calls: str,
    evidence_refs: Iterable[str],
    workspace_id: str = "workspace_demo",
    status: str = "draft",
    created_at: str | None = None,
) -> dict[str, Any]:
    """Attach common artifact metadata and a deterministic content hash."""

    artifact = copy.deepcopy(dict(payload))
    existing_metadata = dict(artifact.get("metadata", {}))
    artifact["metadata"] = {
        **existing_metadata,
        "artifact_id": artifact_id,
        "workspace_id": workspace_id,
        "scenario_id": scenario_id,
        "artifact_type": artifact_type,
        "format": "json",
        "status": status,
        "created_at": created_at or _utc_now(),
        "producer": producer,
        "model_calls": model_calls,
        "evidence_refs": _dedupe(evidence_refs),
    }
    artifact["metadata"]["content_hash"] = artifact_content_hash(artifact)
    return artifact


def artifact_content_hash(artifact: Mapping[str, Any]) -> str:
    """Hash artifact content while excluding the hash field itself."""

    normalized = copy.deepcopy(dict(artifact))
    metadata = dict(normalized.get("metadata", {}))
    metadata.pop("content_hash", None)
    normalized["metadata"] = metadata
    encoded = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def collect_evidence_refs(payload: Any) -> list[str]:
    """Collect evidence references from nested artifact-like data."""

    refs: list[str] = []
    _collect_evidence_refs(payload, refs)
    return _dedupe(refs)


def eval_report_evidence_refs(report: Mapping[str, Any]) -> list[str]:
    refs = collect_evidence_refs(report)
    for scenario in report.get("scenarios", []):
        scenario_id = scenario.get("scenario_id")
        if not scenario_id:
            continue
        for gate in scenario.get("gate_results", {}):
            refs.append(f"gate.{gate}.{scenario_id}.v1")
    return _dedupe(refs)


def build_evidence_registry_payload(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    entries_by_ref: dict[str, dict[str, Any]] = {}
    for path, artifact in artifacts.items():
        metadata = artifact.get("metadata", {})
        if metadata.get("artifact_type") == "evidence_registry":
            continue

        for evidence_ref in collect_evidence_refs(artifact):
            if evidence_ref in entries_by_ref:
                continue
            entries_by_ref[evidence_ref] = {
                "evidence_ref": evidence_ref,
                "workspace_id": metadata.get("workspace_id"),
                "scenario_id": metadata.get("scenario_id"),
                "source_type": _evidence_source_type(evidence_ref),
                "stage": _evidence_stage(evidence_ref),
                "producer": metadata.get("producer"),
                "source_artifact_id": metadata.get("artifact_id"),
                "source_artifact_path": path,
                "content_hash": metadata.get("content_hash"),
            }

    return {
        "registry_version": "evidence_registry.v1",
        "entry_count": len(entries_by_ref),
        "entries": list(entries_by_ref.values()),
    }


def validate_artifact(artifact: Mapping[str, Any]) -> tuple[ArtifactValidationIssue, ...]:
    issues: list[ArtifactValidationIssue] = []
    metadata = artifact.get("metadata")
    if not isinstance(metadata, Mapping):
        return (ArtifactValidationIssue("metadata", "missing_metadata"),)

    for field in REQUIRED_METADATA_FIELDS:
        if field not in metadata:
            issues.append(ArtifactValidationIssue(f"metadata.{field}", "missing_field"))

    if metadata.get("status") not in ALLOWED_STATUSES:
        issues.append(ArtifactValidationIssue("metadata.status", "invalid_status"))
    if metadata.get("format") != "json":
        issues.append(ArtifactValidationIssue("metadata.format", "invalid_format"))
    if metadata.get("model_calls") not in ALLOWED_MODEL_CALLS:
        issues.append(ArtifactValidationIssue("metadata.model_calls", "invalid_model_calls"))

    evidence_refs = metadata.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        issues.append(ArtifactValidationIssue("metadata.evidence_refs", "missing_evidence_refs"))
    elif any(not isinstance(ref, str) or not ref for ref in evidence_refs):
        issues.append(ArtifactValidationIssue("metadata.evidence_refs", "invalid_evidence_ref"))

    if metadata.get("content_hash") != artifact_content_hash(artifact):
        issues.append(ArtifactValidationIssue("metadata.content_hash", "content_hash_mismatch"))

    artifact_type = metadata.get("artifact_type")
    if artifact_type == "runbook":
        issues.extend(_validate_runbook_artifact(artifact))
    elif artifact_type == "eval_report":
        issues.extend(_validate_eval_report_artifact(artifact))
    elif artifact_type == "evidence_registry":
        issues.extend(_validate_evidence_registry_artifact(artifact))
    else:
        issues.append(ArtifactValidationIssue("metadata.artifact_type", "unknown_artifact_type"))

    return tuple(issues)


def validate_artifact_bundle(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> tuple[ArtifactValidationIssue, ...]:
    issues: list[ArtifactValidationIssue] = []
    for path, artifact in artifacts.items():
        for issue in validate_artifact(artifact):
            issues.append(
                ArtifactValidationIssue(
                    path=f"{path}.{issue.path}",
                    issue=issue.issue,
                )
            )
    issues.extend(_validate_bundle_evidence_resolution(artifacts))
    return tuple(issues)


def write_json_artifacts(
    output_root: Path,
    artifacts: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, str]]:
    written = []
    for relative_path, artifact in artifacts.items():
        path = output_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
        written.append(
            {
                "path": str(path),
                "artifact_id": str(artifact["metadata"]["artifact_id"]),
                "content_hash": str(artifact["metadata"]["content_hash"]),
            }
        )
    return written


def _validate_runbook_artifact(
    artifact: Mapping[str, Any],
) -> list[ArtifactValidationIssue]:
    issues = []
    if artifact.get("model_calls") != artifact["metadata"].get("model_calls"):
        issues.append(ArtifactValidationIssue("model_calls", "metadata_model_calls_mismatch"))

    boundary_validation = artifact.get("boundary_validation")
    if not isinstance(boundary_validation, Mapping):
        issues.append(ArtifactValidationIssue("boundary_validation", "missing_boundary_validation"))
    elif boundary_validation.get("passed") is not True:
        issues.append(ArtifactValidationIssue("boundary_validation", "runbook_boundary_failed"))

    claims = artifact.get("claims")
    if not isinstance(claims, list) or not claims:
        issues.append(ArtifactValidationIssue("claims", "missing_claims"))
        return issues

    for index, claim in enumerate(claims):
        evidence_refs = claim.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not evidence_refs:
            issues.append(
                ArtifactValidationIssue(
                    f"claims.{index}.evidence_refs",
                    "missing_claim_evidence_refs",
                )
            )
    return issues


def _validate_eval_report_artifact(
    artifact: Mapping[str, Any],
) -> list[ArtifactValidationIssue]:
    issues = []
    if artifact.get("model_calls") != artifact["metadata"].get("model_calls"):
        issues.append(ArtifactValidationIssue("model_calls", "metadata_model_calls_mismatch"))
    if not isinstance(artifact.get("passed"), bool):
        issues.append(ArtifactValidationIssue("passed", "missing_passed"))

    scenarios = artifact.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        issues.append(ArtifactValidationIssue("scenarios", "missing_scenarios"))
        return issues

    if artifact.get("scenario_count") != len(scenarios):
        issues.append(ArtifactValidationIssue("scenario_count", "scenario_count_mismatch"))

    for index, scenario in enumerate(scenarios):
        if not scenario.get("scenario_id"):
            issues.append(ArtifactValidationIssue(f"scenarios.{index}.scenario_id", "missing_field"))
        if not isinstance(scenario.get("passed"), bool):
            issues.append(ArtifactValidationIssue(f"scenarios.{index}.passed", "missing_passed"))
        if not isinstance(scenario.get("gate_results"), Mapping):
            issues.append(
                ArtifactValidationIssue(
                    f"scenarios.{index}.gate_results",
                    "missing_gate_results",
                )
            )
    return issues


def _validate_evidence_registry_artifact(
    artifact: Mapping[str, Any],
) -> list[ArtifactValidationIssue]:
    issues = []
    entries = artifact.get("entries")
    if not isinstance(entries, list) or not entries:
        return [ArtifactValidationIssue("entries", "missing_registry_entries")]

    refs = []
    required_entry_fields = (
        "evidence_ref",
        "workspace_id",
        "scenario_id",
        "source_type",
        "stage",
        "producer",
        "source_artifact_id",
        "source_artifact_path",
        "content_hash",
    )
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            issues.append(ArtifactValidationIssue(f"entries.{index}", "invalid_registry_entry"))
            continue

        for field in required_entry_fields:
            if not entry.get(field):
                issues.append(
                    ArtifactValidationIssue(
                        f"entries.{index}.{field}",
                        "missing_field",
                    )
                )
        evidence_ref = entry.get("evidence_ref")
        if evidence_ref:
            refs.append(str(evidence_ref))

    if len(set(refs)) != len(refs):
        issues.append(ArtifactValidationIssue("entries", "duplicate_evidence_ref"))
    if artifact.get("entry_count") != len(entries):
        issues.append(ArtifactValidationIssue("entry_count", "entry_count_mismatch"))
    return issues


def _validate_bundle_evidence_resolution(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> list[ArtifactValidationIssue]:
    registry = _bundle_registry(artifacts)
    if registry is None:
        return []

    registry_refs = {
        entry.get("evidence_ref")
        for entry in registry.get("entries", [])
        if isinstance(entry, Mapping)
    }
    issues = []
    for path, artifact in artifacts.items():
        metadata = artifact.get("metadata", {})
        if metadata.get("artifact_type") == "evidence_registry":
            continue
        for evidence_ref in metadata.get("evidence_refs", []):
            if evidence_ref not in registry_refs:
                issues.append(
                    ArtifactValidationIssue(
                        path=f"{path}.metadata.evidence_refs",
                        issue="unresolved_evidence_ref",
                    )
                )
    return issues


def _bundle_registry(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    for artifact in artifacts.values():
        metadata = artifact.get("metadata", {})
        if metadata.get("artifact_type") == "evidence_registry":
            return artifact
    return None


def _collect_evidence_refs(value: Any, refs: list[str]) -> None:
    if isinstance(value, Mapping):
        evidence_ref = value.get("evidence_ref")
        if isinstance(evidence_ref, str):
            refs.append(evidence_ref)

        evidence_refs = value.get("evidence_refs")
        if isinstance(evidence_refs, list):
            refs.extend(ref for ref in evidence_refs if isinstance(ref, str))

        for child in value.values():
            _collect_evidence_refs(child, refs)
    elif isinstance(value, list):
        for child in value:
            _collect_evidence_refs(child, refs)


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


def _evidence_source_type(evidence_ref: str) -> str:
    if evidence_ref.startswith("validation."):
        return "validation_result"
    if evidence_ref.startswith("schema.data_check."):
        return "schema_data_check"
    if evidence_ref.startswith("schema.diff."):
        return "schema_diff"
    if evidence_ref.startswith("gate."):
        return "gate_result"
    if evidence_ref.startswith("artifact."):
        return "artifact"
    if evidence_ref.startswith("audit."):
        return "audit_event"
    if evidence_ref.startswith("approval."):
        return "approval_event"
    if evidence_ref.startswith("finding."):
        return "detector_finding"
    if evidence_ref.startswith("tool."):
        return "tool_output"
    return "unknown"


def _evidence_stage(evidence_ref: str) -> str:
    if evidence_ref.startswith("validation."):
        return "validation"
    if evidence_ref.startswith("schema."):
        return "schema_introspection"
    if evidence_ref.startswith("gate."):
        return "gatekeeper"
    if evidence_ref.startswith("artifact."):
        return "artifact_store"
    if evidence_ref.startswith("audit."):
        return "audit"
    if evidence_ref.startswith("approval."):
        return "approval"
    if evidence_ref.startswith("tool."):
        return "tool"
    if evidence_ref.startswith("finding."):
        return "finding"
    return "unknown"
