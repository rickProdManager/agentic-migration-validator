import unittest

from tools.audit import (
    build_audit_event,
    validate_audit_event,
    validate_audit_log,
)


BASE_EVENT = {
    "audit_event_id": "audit.validation.checksum.public_customers.v1",
    "workflow_run_id": "workflow.fixture_validation.20260630_120000",
    "workspace_id": "workspace_demo",
    "scenario_id": "failed_checksum",
    "actor_name": "checksum_validation",
    "actor_type": "tool",
    "stage": "validation",
    "created_at": "2026-06-30T12:00:00Z",
}


def audit_event(**overrides):
    event = build_audit_event(
        **BASE_EVENT,
        decision="tool_called",
        status="completed",
        evidence_refs=["validation.checksum.public.customers.v1"],
        output_summary="Compared source and target checksums.",
    )
    event.update(overrides)
    return event


class AuditTest(unittest.TestCase):
    def test_build_audit_event_creates_valid_event(self):
        event = audit_event()

        self.assertEqual(event["audit_schema_version"], "audit_event.v1")
        self.assertEqual(event["workflow_run_id"], BASE_EVENT["workflow_run_id"])
        self.assertEqual(validate_audit_event(event), ())

    def test_finding_event_requires_finding_and_evidence_links(self):
        event = audit_event(
            decision="finding_emitted",
            evidence_refs=[],
            finding_keys=[],
        )

        issues = validate_audit_event(event)

        self.assertIn("missing_finding_link", {issue.issue for issue in issues})
        self.assertIn("missing_evidence_link", {issue.issue for issue in issues})

    def test_gate_event_requires_gate_name(self):
        event = audit_event(
            decision="gate_blocked",
            status="blocked",
            finding_keys=["validation.checksum_mismatch:public.customers:*"],
        )

        issues = validate_audit_event(event)

        self.assertIn("missing_gate", {issue.issue for issue in issues})

    def test_approval_event_requires_approval_id(self):
        event = audit_event(
            decision="approval_recorded",
            actor_name="operator",
            actor_type="human",
            status="recorded",
        )

        issues = validate_audit_event(event)

        self.assertIn("missing_approval_id", {issue.issue for issue in issues})

    def test_artifact_event_requires_artifact_link(self):
        event = audit_event(
            decision="artifact_generated",
            status="completed",
            artifact_ids=[],
        )

        issues = validate_audit_event(event)

        self.assertIn("missing_artifact_link", {issue.issue for issue in issues})

    def test_confidence_basis_requires_evidence_link(self):
        event = audit_event(
            evidence_refs=[],
            confidence_basis="Exact checksum over all rows.",
        )

        issues = validate_audit_event(event)

        self.assertIn("missing_evidence_link", {issue.issue for issue in issues})

    def test_link_fields_must_be_string_lists(self):
        event = audit_event(evidence_refs=["valid", 123])

        issues = validate_audit_event(event)

        self.assertIn("invalid_link_list", {issue.issue for issue in issues})

    def test_validate_audit_log_rejects_duplicate_event_ids(self):
        event = audit_event()

        issues = validate_audit_log([event, dict(event)])

        self.assertIn("duplicate_audit_event_id", {issue.issue for issue in issues})


if __name__ == "__main__":
    unittest.main()
