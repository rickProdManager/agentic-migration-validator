"""Evidence-bound runbook draft generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


RUNBOOK_BOUNDARY_VERSION = "runbook_advisor_boundary.v1"
UNSUPPORTED_CAUSAL_PATTERNS = (
    "caused by",
    "root cause",
    "during transfer",
    "data corruption",
    "corruption",
    "data loss",
    "lost data",
    "because of",
)


@dataclass(frozen=True)
class RunbookBoundaryIssue:
    claim_key: str
    issue: str

    def to_dict(self) -> dict[str, str]:
        return {"claim_key": self.claim_key, "issue": self.issue}


def generate_runbook_draft(
    *,
    scenario_id: str,
    validation_findings: Iterable[Mapping[str, Any]] = (),
    schema_findings: Iterable[Mapping[str, Any]] = (),
    schema_data_check_results: Iterable[Mapping[str, Any]] = (),
    gate_results: Mapping[str, Mapping[str, Any]] | None = None,
    model_narrative: str | None = None,
) -> dict[str, Any]:
    """Generate a deterministic runbook draft from structured workflow outputs."""

    findings = tuple(validation_findings) + tuple(schema_findings)
    gates = dict(gate_results or {})
    claims = [
        *_gate_claims(scenario_id, gates),
        *_finding_claims(findings),
        *_data_check_claims(schema_data_check_results),
        *_recommendation_claims(scenario_id, gates, findings),
    ]
    if model_narrative is not None:
        claims.append(_model_narrative_claim(scenario_id, model_narrative, gates, findings))

    runbook = {
        "metadata": {
            "artifact_id": f"artifact.runbook_draft.{scenario_id}.v1",
            "scenario_id": scenario_id,
            "artifact_type": "runbook",
            "format": "json",
            "status": "draft",
            "producer": "runbook_advisor",
            "model_calls": "enabled" if model_narrative is not None else "disabled",
            "boundary_version": RUNBOOK_BOUNDARY_VERSION,
            "evidence_refs": _unique_evidence_refs(claims),
        },
        "title": f"Migration Runbook Draft: {scenario_id}",
        "model_calls": "enabled" if model_narrative is not None else "disabled",
        "summary": _summary(gates),
        "claims": claims,
        "sections": _sections(scenario_id, claims),
        "approval_checkpoints": [
            "validation_acceptance",
            "cutover_recommendation",
            "readiness",
        ],
    }
    issues = validate_runbook_boundary(runbook)
    runbook["boundary_validation"] = {
        "passed": not issues,
        "issues": [issue.to_dict() for issue in issues],
    }
    return runbook


def validate_runbook_boundary(runbook: Mapping[str, Any]) -> tuple[RunbookBoundaryIssue, ...]:
    """Validate that runbook claims have the evidence required by the boundary."""

    issues = []
    supported_text = _supported_evidence_text(runbook.get("claims", ()))
    for claim in runbook.get("claims", []):
        claim_key = str(claim.get("claim_key", "<missing>"))
        evidence_refs = tuple(claim.get("evidence_refs", ()))
        claim_type = claim.get("claim_type")

        if not evidence_refs:
            issues.append(RunbookBoundaryIssue(claim_key, "missing_evidence_refs"))
        if claim_type in {"gate_status", "recommendation"} and not _has_gate_ref(evidence_refs):
            issues.append(RunbookBoundaryIssue(claim_key, "missing_gate_evidence_ref"))
        if claim_type == "finding_summary" and not claim.get("finding_keys"):
            issues.append(RunbookBoundaryIssue(claim_key, "missing_finding_key"))
        if _has_unsupported_causal_language(str(claim.get("claim", "")), supported_text):
            issues.append(RunbookBoundaryIssue(claim_key, "unsupported_causal_language"))
    return tuple(issues)


def build_live_model_prompt(runbook: Mapping[str, Any]) -> str:
    """Build the constrained prompt used for optional live advisor prose."""

    return (
        "You are drafting a migration runbook note from deterministic evidence.\n"
        "Use only the JSON evidence below.\n"
        "Do not decide safety; gate_results already decide safety.\n"
        "Do not claim root cause, data corruption, data loss, or transfer failure unless the evidence says that exact thing.\n"
        "If the evidence is insufficient, write 'insufficient evidence'.\n"
        "Return one short paragraph and nothing else.\n\n"
        f"{_json_dumps(runbook)}"
    )


def _gate_claims(
    scenario_id: str,
    gate_results: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    claims = []
    for gate in ("can_recommend_cutover", "can_mark_ready"):
        result = gate_results.get(gate)
        evidence_ref = _gate_ref(scenario_id, gate)
        if result is None:
            claims.append(
                {
                    "claim_key": f"{gate}.insufficient_evidence",
                    "claim_type": "gate_status",
                    "claim": f"insufficient evidence: {gate} result is unavailable.",
                    "evidence_refs": [evidence_ref],
                    "finding_keys": [],
                }
            )
            continue

        allowed = bool(result.get("allowed"))
        status = "allowed" if allowed else "blocked"
        blocking_findings = list(result.get("blocking_findings", []))
        claims.append(
            {
                "claim_key": f"{gate}.{status}",
                "claim_type": "gate_status",
                "claim": f"{gate} is {status}.",
                "evidence_refs": [evidence_ref],
                "finding_keys": blocking_findings,
            }
        )
    return claims


def _finding_claims(findings: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    claims = []
    for finding in findings:
        finding_key = str(finding.get("finding_key"))
        summary = finding.get("summary") or f"Finding {finding_key} is present."
        evidence_refs = list(finding.get("evidence_refs", ())) or [_finding_ref(finding_key)]
        claims.append(
            {
                "claim_key": f"finding.{finding_key}",
                "claim_type": "finding_summary",
                "claim": str(summary),
                "evidence_refs": evidence_refs,
                "finding_keys": [finding_key],
                "severity": finding.get("severity"),
                "risk_axis": finding.get("risk_axis"),
            }
        )
    return claims


def _data_check_claims(
    data_check_results: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    claims = []
    for check in data_check_results:
        check_type = str(check.get("check_type"))
        evidence_ref = str(check.get("evidence_ref"))
        passed = bool(check.get("passed"))
        status = "passed" if passed else "failed"
        claims.append(
            {
                "claim_key": f"data_check.{check_type}.{status}",
                "claim_type": "data_check_summary",
                "claim": f"{check_type} {status}.",
                "evidence_refs": [evidence_ref],
                "finding_keys": [],
            }
        )
    return claims


def _recommendation_claims(
    scenario_id: str,
    gate_results: Mapping[str, Mapping[str, Any]],
    findings: tuple[Mapping[str, Any], ...],
) -> list[dict[str, Any]]:
    claims = []
    findings_by_key = {
        finding.get("finding_key"): finding for finding in findings if finding.get("finding_key")
    }

    for gate in ("can_recommend_cutover", "can_mark_ready"):
        result = gate_results.get(gate)
        evidence_ref = _gate_ref(scenario_id, gate)
        if result is None:
            claims.append(
                {
                    "claim_key": f"recommendation.{gate}.insufficient_evidence",
                    "claim_type": "recommendation",
                    "claim": f"insufficient evidence: no recommendation can be made for {gate}.",
                    "evidence_refs": [evidence_ref],
                    "finding_keys": [],
                }
            )
            continue

        blocking_findings = list(result.get("blocking_findings", []))
        if result.get("allowed"):
            claims.append(
                {
                    "claim_key": f"recommendation.{gate}.allowed",
                    "claim_type": "recommendation",
                    "claim": f"{gate} is allowed by deterministic gates; continue only through required approvals.",
                    "evidence_refs": [evidence_ref],
                    "finding_keys": [],
                }
            )
            continue

        evidence_refs = [evidence_ref]
        for finding_key in blocking_findings:
            evidence_refs.extend(findings_by_key.get(finding_key, {}).get("evidence_refs", ()))
        claims.append(
            {
                "claim_key": f"recommendation.{gate}.blocked",
                "claim_type": "recommendation",
                "claim": f"Do not proceed through {gate} until blocking findings are resolved or accepted through the workflow.",
                "evidence_refs": _dedupe(evidence_refs),
                "finding_keys": blocking_findings,
            }
        )

    return claims


def _model_narrative_claim(
    scenario_id: str,
    narrative: str,
    gate_results: Mapping[str, Mapping[str, Any]],
    findings: tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    evidence_refs = []
    for gate in ("can_recommend_cutover", "can_mark_ready"):
        if gate in gate_results:
            evidence_refs.append(_gate_ref(scenario_id, gate))
    finding_keys = []
    for finding in findings:
        finding_key = finding.get("finding_key")
        if finding_key:
            finding_keys.append(str(finding_key))
            evidence_refs.extend(finding.get("evidence_refs", ()))
    if not evidence_refs:
        evidence_refs = [_gate_ref(scenario_id, "can_mark_ready")]
    return {
        "claim_key": "model.narrative",
        "claim_type": "contextualization",
        "claim": narrative,
        "evidence_refs": _dedupe(evidence_refs),
        "finding_keys": _dedupe(finding_keys),
    }


def _summary(gate_results: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    cutover = gate_results.get("can_recommend_cutover")
    ready = gate_results.get("can_mark_ready")
    return {
        "can_recommend_cutover": None if cutover is None else bool(cutover.get("allowed")),
        "can_mark_ready": None if ready is None else bool(ready.get("allowed")),
        "blocking_findings": _dedupe(
            [
                *list((cutover or {}).get("blocking_findings", ())),
                *list((ready or {}).get("blocking_findings", ())),
            ]
        ),
    }


def _sections(scenario_id: str, claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gate_claims = [claim for claim in claims if claim["claim_type"] == "gate_status"]
    finding_claims = [claim for claim in claims if claim["claim_type"] == "finding_summary"]
    recommendation_claims = [
        claim for claim in claims if claim["claim_type"] == "recommendation"
    ]
    return [
        {
            "section_id": "gate_status",
            "title": "Gate Status",
            "body_markdown": _claims_to_markdown(gate_claims),
            "evidence_refs": _unique_evidence_refs(gate_claims),
        },
        {
            "section_id": "findings",
            "title": "Findings",
            "body_markdown": _claims_to_markdown(finding_claims)
            if finding_claims
            else f"No detector findings are present for {scenario_id}.",
            "evidence_refs": _unique_evidence_refs(finding_claims),
        },
        {
            "section_id": "recommended_actions",
            "title": "Recommended Actions",
            "body_markdown": _claims_to_markdown(recommendation_claims),
            "evidence_refs": _unique_evidence_refs(recommendation_claims),
        },
    ]


def _claims_to_markdown(claims: list[dict[str, Any]]) -> str:
    if not claims:
        return "insufficient evidence"
    return "\n".join(f"- {claim['claim']}" for claim in claims)


def _supported_evidence_text(claims: Iterable[Mapping[str, Any]]) -> str:
    supported_claims = [
        str(claim.get("claim", ""))
        for claim in claims
        if claim.get("claim_type") != "contextualization"
    ]
    return " ".join(supported_claims).lower()


def _has_unsupported_causal_language(text: str, supported_text: str) -> bool:
    normalized = text.lower()
    return any(
        pattern in normalized and pattern not in supported_text
        for pattern in UNSUPPORTED_CAUSAL_PATTERNS
    )


def _json_dumps(payload: Mapping[str, Any]) -> str:
    import json

    return json.dumps(payload, indent=2, sort_keys=True)


def _unique_evidence_refs(claims: Iterable[Mapping[str, Any]]) -> list[str]:
    refs = []
    for claim in claims:
        refs.extend(claim.get("evidence_refs", ()))
    return _dedupe(refs)


def _dedupe(values: Iterable[Any]) -> list[Any]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _has_gate_ref(evidence_refs: Iterable[str]) -> bool:
    return any(str(evidence_ref).startswith("gate.") for evidence_ref in evidence_refs)


def _gate_ref(scenario_id: str, gate: str) -> str:
    return f"gate.{gate}.{scenario_id}.v1"


def _finding_ref(finding_key: str) -> str:
    return "finding." + finding_key.replace(":", ".").replace("*", "star") + ".v1"
