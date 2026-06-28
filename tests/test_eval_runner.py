import unittest

from tools.eval_runner import evaluate_findings


SCOPE = {
    "schema": "public",
    "table": "customers",
    "column": None,
    "constraint": None,
    "business_key": None,
}


def finding(
    finding_key="validation.checksum_mismatch:public.customers:*",
    *,
    risk_axis="migration_integrity",
    severity="high",
    scope=None,
    record_type="detector_finding",
):
    return {
        "record_type": record_type,
        "risk_axis": risk_axis,
        "finding_key": finding_key,
        "finding_type": "validation.checksum_mismatch",
        "detector": "canonical_checksum",
        "severity": severity,
        "scope": SCOPE if scope is None else scope,
    }


class EvalRunnerTest(unittest.TestCase):
    def test_detects_matching_expected_finding(self):
        result = evaluate_findings(
            expected_findings=[finding()],
            produced_findings=[finding()],
        )

        self.assertTrue(result.passed)
        self.assertEqual(
            result.detected,
            ({"finding_key": "validation.checksum_mismatch:public.customers:*"},),
        )
        self.assertEqual(result.missed, ())
        self.assertEqual(result.false_positives, ())

    def test_reports_missed_expected_finding(self):
        result = evaluate_findings(
            expected_findings=[finding()],
            produced_findings=[],
        )

        self.assertFalse(result.passed)
        self.assertEqual(
            result.missed[0]["finding_key"],
            "validation.checksum_mismatch:public.customers:*",
        )

    def test_reports_false_positive_finding(self):
        result = evaluate_findings(
            expected_findings=[],
            produced_findings=[finding()],
        )

        self.assertFalse(result.passed)
        self.assertEqual(
            result.false_positives[0]["finding_key"],
            "validation.checksum_mismatch:public.customers:*",
        )

    def test_allowed_extra_finding_is_not_false_positive(self):
        result = evaluate_findings(
            expected_findings=[],
            produced_findings=[finding()],
            allowed_extra_findings=["validation.checksum_mismatch:public.customers:*"],
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.false_positives, ())

    def test_reports_severity_mismatch(self):
        result = evaluate_findings(
            expected_findings=[finding(severity="high")],
            produced_findings=[finding(severity="critical")],
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.severity_mismatches[0]["expected"], "high")
        self.assertEqual(result.severity_mismatches[0]["actual"], "critical")

    def test_reports_scope_mismatch(self):
        produced_scope = {**SCOPE, "table": "orders"}
        result = evaluate_findings(
            expected_findings=[finding(scope=SCOPE)],
            produced_findings=[finding(scope=produced_scope)],
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.scope_mismatches[0]["expected"], SCOPE)
        self.assertEqual(result.scope_mismatches[0]["actual"], produced_scope)

    def test_reports_axis_mismatch(self):
        result = evaluate_findings(
            expected_findings=[finding(risk_axis="migration_integrity")],
            produced_findings=[finding(risk_axis="compatibility_advisory")],
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.axis_mismatches[0]["expected"], "migration_integrity")
        self.assertEqual(result.axis_mismatches[0]["actual"], "compatibility_advisory")

    def test_ignores_non_detector_records_for_detection_eval(self):
        result = evaluate_findings(
            expected_findings=[],
            produced_findings=[
                finding(
                    finding_key="gate.required_approval_missing:validation:*",
                    record_type="gate_finding",
                )
            ],
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.false_positives, ())


if __name__ == "__main__":
    unittest.main()
