import unittest

from tools.artifacts import (
    build_artifact,
    build_evidence_registry_payload,
    collect_evidence_refs,
    eval_report_evidence_refs,
    validate_artifact,
    validate_artifact_bundle,
)


CREATED_AT = "2026-06-29T12:00:00Z"


def sample_runbook():
    return {
        "model_calls": "disabled",
        "boundary_validation": {"passed": True, "issues": []},
        "claims": [
            {
                "claim_key": "can_mark_ready.blocked",
                "claim_type": "gate_status",
                "claim": "can_mark_ready is blocked.",
                "evidence_refs": ["gate.can_mark_ready.failed_checksum.v1"],
                "finding_keys": ["validation.checksum_mismatch:public.customers:*"],
            }
        ],
        "sections": [],
    }


def sample_eval_report():
    return {
        "model_calls": "disabled",
        "passed": True,
        "scenario_count": 1,
        "scenarios": [
            {
                "scenario_id": "failed_checksum",
                "passed": True,
                "validation_findings": [
                    {
                        "finding_key": "validation.checksum_mismatch:public.customers:*",
                        "evidence_refs": ["validation.checksum.public.customers.v1"],
                    }
                ],
                "schema_findings": [],
                "schema_data_check_results": [],
                "gate_results": {
                    "can_mark_ready": {
                        "allowed": False,
                        "blocking_findings": [
                            "validation.checksum_mismatch:public.customers:*"
                        ],
                    }
                },
            }
        ],
    }


def build_sample_bundle():
    eval_report = sample_eval_report()
    return {
        "eval_report.json": build_artifact(
            eval_report,
            artifact_id="artifact.eval_report.fixture_suite.v1",
            artifact_type="eval_report",
            scenario_id="fixture_suite",
            producer="eval_runner",
            model_calls="disabled",
            evidence_refs=eval_report_evidence_refs(eval_report),
            status="accepted",
            created_at=CREATED_AT,
        ),
        "scenarios/failed_checksum/runbook.json": build_artifact(
            sample_runbook(),
            artifact_id="artifact.runbook_draft.failed_checksum.v1",
            artifact_type="runbook",
            scenario_id="failed_checksum",
            producer="runbook_advisor",
            model_calls="disabled",
            evidence_refs=["gate.can_mark_ready.failed_checksum.v1"],
            created_at=CREATED_AT,
        ),
    }


class ArtifactTest(unittest.TestCase):
    def test_build_artifact_adds_metadata_and_valid_content_hash(self):
        artifact = build_artifact(
            sample_runbook(),
            artifact_id="artifact.runbook_draft.failed_checksum.v1",
            artifact_type="runbook",
            scenario_id="failed_checksum",
            producer="runbook_advisor",
            model_calls="disabled",
            evidence_refs=["gate.can_mark_ready.failed_checksum.v1"],
            created_at=CREATED_AT,
        )

        self.assertEqual(artifact["metadata"]["format"], "json")
        self.assertTrue(artifact["metadata"]["content_hash"].startswith("sha256:"))
        self.assertEqual(validate_artifact(artifact), ())

    def test_validate_artifact_rejects_content_hash_mismatch(self):
        artifact = build_artifact(
            sample_runbook(),
            artifact_id="artifact.runbook_draft.failed_checksum.v1",
            artifact_type="runbook",
            scenario_id="failed_checksum",
            producer="runbook_advisor",
            model_calls="disabled",
            evidence_refs=["gate.can_mark_ready.failed_checksum.v1"],
            created_at=CREATED_AT,
        )
        artifact["claims"][0]["claim"] = "Edited after hashing."

        issues = validate_artifact(artifact)

        self.assertIn("content_hash_mismatch", {issue.issue for issue in issues})

    def test_validate_artifact_rejects_failed_runbook_boundary(self):
        runbook = sample_runbook()
        runbook["boundary_validation"] = {
            "passed": False,
            "issues": [{"claim_key": "model.narrative", "issue": "unsupported"}],
        }
        artifact = build_artifact(
            runbook,
            artifact_id="artifact.runbook_draft.failed_checksum.v1",
            artifact_type="runbook",
            scenario_id="failed_checksum",
            producer="runbook_advisor",
            model_calls="disabled",
            evidence_refs=["gate.can_mark_ready.failed_checksum.v1"],
            created_at=CREATED_AT,
        )

        issues = validate_artifact(artifact)

        self.assertIn("runbook_boundary_failed", {issue.issue for issue in issues})

    def test_validate_artifact_rejects_runbook_claim_without_evidence(self):
        runbook = sample_runbook()
        runbook["claims"][0]["evidence_refs"] = []
        artifact = build_artifact(
            runbook,
            artifact_id="artifact.runbook_draft.failed_checksum.v1",
            artifact_type="runbook",
            scenario_id="failed_checksum",
            producer="runbook_advisor",
            model_calls="disabled",
            evidence_refs=["gate.can_mark_ready.failed_checksum.v1"],
            created_at=CREATED_AT,
        )

        issues = validate_artifact(artifact)

        self.assertIn("missing_claim_evidence_refs", {issue.issue for issue in issues})

    def test_eval_report_evidence_refs_include_findings_and_gate_results(self):
        refs = eval_report_evidence_refs(sample_eval_report())

        self.assertEqual(
            refs,
            [
                "validation.checksum.public.customers.v1",
                "gate.can_mark_ready.failed_checksum.v1",
            ],
        )

    def test_validate_artifact_rejects_eval_scenario_count_mismatch(self):
        report = sample_eval_report()
        report["scenario_count"] = 2
        artifact = build_artifact(
            report,
            artifact_id="artifact.eval_report.fixture_suite.v1",
            artifact_type="eval_report",
            scenario_id="fixture_suite",
            producer="eval_runner",
            model_calls="disabled",
            evidence_refs=eval_report_evidence_refs(report),
            status="accepted",
            created_at=CREATED_AT,
        )

        issues = validate_artifact(artifact)

        self.assertIn("scenario_count_mismatch", {issue.issue for issue in issues})

    def test_validate_artifact_bundle_prefixes_issue_paths(self):
        runbook = sample_runbook()
        runbook["claims"][0]["evidence_refs"] = []
        artifact = build_artifact(
            runbook,
            artifact_id="artifact.runbook_draft.failed_checksum.v1",
            artifact_type="runbook",
            scenario_id="failed_checksum",
            producer="runbook_advisor",
            model_calls="disabled",
            evidence_refs=["gate.can_mark_ready.failed_checksum.v1"],
            created_at=CREATED_AT,
        )

        issues = validate_artifact_bundle(
            {"scenarios/failed_checksum/runbook.json": artifact}
        )

        self.assertEqual(
            issues[0].path,
            "scenarios/failed_checksum/runbook.json.claims.0.evidence_refs",
        )

    def test_collect_evidence_refs_deduplicates_nested_refs(self):
        refs = collect_evidence_refs(
            {
                "evidence_refs": ["a", "b"],
                "nested": [{"evidence_ref": "a"}, {"evidence_refs": ["c"]}],
            }
        )

        self.assertEqual(refs, ["a", "b", "c"])

    def test_build_evidence_registry_payload_maps_refs_to_source_artifacts(self):
        payload = build_evidence_registry_payload(build_sample_bundle())
        entries_by_ref = {entry["evidence_ref"]: entry for entry in payload["entries"]}

        self.assertEqual(payload["registry_version"], "evidence_registry.v1")
        self.assertEqual(payload["entry_count"], len(payload["entries"]))
        self.assertEqual(
            entries_by_ref["validation.checksum.public.customers.v1"]["source_type"],
            "validation_result",
        )
        self.assertEqual(
            entries_by_ref["gate.can_mark_ready.failed_checksum.v1"]["stage"],
            "gatekeeper",
        )

    def test_validate_artifact_accepts_evidence_registry_artifact(self):
        bundle = build_sample_bundle()
        payload = build_evidence_registry_payload(bundle)
        registry = build_artifact(
            payload,
            artifact_id="artifact.evidence_registry.fixture_suite.v1",
            artifact_type="evidence_registry",
            scenario_id="fixture_suite",
            producer="artifact_writer",
            model_calls="disabled",
            evidence_refs=[entry["evidence_ref"] for entry in payload["entries"]],
            status="accepted",
            created_at=CREATED_AT,
        )

        self.assertEqual(validate_artifact(registry), ())

    def test_validate_artifact_rejects_duplicate_registry_entries(self):
        bundle = build_sample_bundle()
        payload = build_evidence_registry_payload(bundle)
        payload["entries"].append(dict(payload["entries"][0]))
        payload["entry_count"] = len(payload["entries"])
        registry = build_artifact(
            payload,
            artifact_id="artifact.evidence_registry.fixture_suite.v1",
            artifact_type="evidence_registry",
            scenario_id="fixture_suite",
            producer="artifact_writer",
            model_calls="disabled",
            evidence_refs=[entry["evidence_ref"] for entry in payload["entries"]],
            status="accepted",
            created_at=CREATED_AT,
        )

        issues = validate_artifact(registry)

        self.assertIn("duplicate_evidence_ref", {issue.issue for issue in issues})

    def test_validate_artifact_bundle_rejects_unresolved_registry_reference(self):
        bundle = build_sample_bundle()
        payload = build_evidence_registry_payload(bundle)
        payload["entries"] = [
            entry
            for entry in payload["entries"]
            if entry["evidence_ref"] != "gate.can_mark_ready.failed_checksum.v1"
        ]
        payload["entry_count"] = len(payload["entries"])
        bundle["evidence_registry.json"] = build_artifact(
            payload,
            artifact_id="artifact.evidence_registry.fixture_suite.v1",
            artifact_type="evidence_registry",
            scenario_id="fixture_suite",
            producer="artifact_writer",
            model_calls="disabled",
            evidence_refs=[entry["evidence_ref"] for entry in payload["entries"]],
            status="accepted",
            created_at=CREATED_AT,
        )

        issues = validate_artifact_bundle(bundle)

        self.assertIn("unresolved_evidence_ref", {issue.issue for issue in issues})


if __name__ == "__main__":
    unittest.main()
