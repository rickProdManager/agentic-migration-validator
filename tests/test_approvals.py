import unittest

from tools.approvals import (
    build_approval_audit_event,
    build_approval_record,
    effective_approvals,
    validate_approval_record,
)
from tools.audit import validate_audit_event
from tools.gatekeeper import GateContext, evaluate_gate


def approval_record(**overrides):
    record = build_approval_record(
        workflow_run_id="workflow.fixture_validation.20260630_120000",
        workspace_id="workspace_demo",
        scenario_id="clean_migration",
        gate="can_accept_validation",
        actor="human.reviewer",
        decision="approved",
        evidence_refs=["artifact.eval_report.fixture_suite.v1"],
        created_at="2026-06-30T12:00:00Z",
    )
    record.update(overrides)
    return record


class ApprovalsTest(unittest.TestCase):
    def test_build_approval_record_matches_gate_approval_type(self):
        record = approval_record()

        self.assertEqual(record["approval_schema_version"], "approval_record.v1")
        self.assertEqual(record["approval_type"], "validation_acceptance")
        self.assertEqual(validate_approval_record(record), ())

    def test_approved_record_satisfies_gate_context(self):
        approvals = effective_approvals([approval_record()])

        result = evaluate_gate(
            "can_accept_validation",
            [],
            GateContext(validation_completed=True, approvals=approvals),
        )

        self.assertTrue(result.allowed)

    def test_approval_type_must_match_gate(self):
        record = approval_record(approval_type="ready")

        issues = validate_approval_record(record)

        self.assertIn("gate_approval_mismatch", {issue.issue for issue in issues})

    def test_approved_record_requires_evidence(self):
        record = approval_record(evidence_refs=[])

        issues = validate_approval_record(record)

        self.assertIn("missing_approval_evidence", {issue.issue for issue in issues})
        self.assertEqual(effective_approvals([record]), ())

    def test_revoked_approval_stops_counting(self):
        approved = approval_record(created_at="2026-06-30T12:00:00Z")
        revoked = approval_record(
            decision="revoked",
            created_at="2026-06-30T12:01:00Z",
        )

        approvals = effective_approvals([approved, revoked])

        self.assertEqual(approvals, ())

    def test_approval_audit_event_is_valid(self):
        event = build_approval_audit_event(approval_record())

        self.assertEqual(event["decision"], "approval_recorded")
        self.assertEqual(event["approval_id"], "approval.validation_acceptance.workspace_demo.clean_migration.v1")
        self.assertEqual(event["gate"], "can_accept_validation")
        self.assertEqual(validate_audit_event(event), ())


if __name__ == "__main__":
    unittest.main()
