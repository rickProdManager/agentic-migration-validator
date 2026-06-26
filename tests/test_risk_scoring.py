import unittest

from tools.risk_scoring import (
    Finding,
    RiskScoringError,
    band_for_score,
    round_half_up,
    score_finding,
    score_risk_axes,
)


class RiskScoringTest(unittest.TestCase):
    def test_per_finding_vectors(self):
        cases = [
            (
                Finding(
                    record_type="detector_finding",
                    risk_axis="migration_integrity",
                    finding_type="validation.checksum_mismatch",
                    blast_radius_multiplier=1.5,
                ),
                53,
                "high",
                "high",
            ),
            (
                Finding(
                    record_type="detector_finding",
                    risk_axis="migration_integrity",
                    finding_type="validation.null_distribution_mismatch",
                    blast_radius_multiplier=1.0,
                ),
                12,
                "moderate",
                "moderate",
            ),
            (
                Finding(
                    record_type="detector_finding",
                    risk_axis="migration_integrity",
                    finding_type="validation.duplicate_business_key",
                    blast_radius_multiplier=1.25,
                ),
                25,
                "high",
                "high",
            ),
            (
                Finding(
                    record_type="detector_finding",
                    risk_axis="migration_integrity",
                    finding_type="schema.missing_primary_key",
                    blast_radius_multiplier=1.5,
                ),
                38,
                "high",
                "high",
            ),
            (
                Finding(
                    record_type="detector_finding",
                    risk_axis="migration_integrity",
                    finding_type="validation.missing_rows",
                    blast_radius_multiplier=2.0,
                    instance_bonus=8,
                ),
                60,
                "critical",
                "critical",
            ),
            (
                Finding(
                    record_type="detector_finding",
                    risk_axis="migration_integrity",
                    finding_type="schema.missing_constraint",
                    blast_radius_multiplier=1.25,
                    instance_bonus=4,
                ),
                23,
                "moderate",
                "moderate",
            ),
        ]

        for finding, expected_points, expected_severity, expected_band in cases:
            with self.subTest(finding=finding.finding_type):
                scored = score_finding(finding)

                self.assertEqual(scored.risk_points, expected_points)
                self.assertEqual(scored.severity, expected_severity)
                self.assertEqual(band_for_score(scored.axis_score_floor), expected_band)

    def test_round_half_up_canary(self):
        self.assertEqual(round_half_up(52.5), 53)

    def test_clean_integrity_scores_zero(self):
        result = score_risk_axes([])

        self.assertEqual(result.axes["migration_integrity"].score, 0)
        self.assertEqual(result.axes["migration_integrity"].band, "low")

    def test_clean_with_advisory_keeps_integrity_low(self):
        result = score_risk_axes(
            [
                Finding(
                    record_type="detector_finding",
                    risk_axis="compatibility_advisory",
                    finding_type="compatibility.unsupported_feature_outside_critical_path",
                )
            ]
        )

        self.assertEqual(result.axes["migration_integrity"].score, 0)
        self.assertEqual(result.axes["migration_integrity"].band, "low")
        self.assertEqual(result.axes["compatibility_advisory"].score, 8)
        self.assertEqual(result.axes["compatibility_advisory"].band, "low")
        self.assertEqual(result.cutover_ready_risk_axes, ("migration_integrity", "process_control"))

    def test_process_missing_approval_uses_moderate_floor(self):
        result = score_risk_axes(
            [
                Finding(
                    record_type="gate_finding",
                    risk_axis="process_control",
                    finding_type="gate.required_approval_missing",
                )
            ]
        )

        self.assertEqual(result.axes["process_control"].score, 25)
        self.assertEqual(result.axes["process_control"].band, "moderate")

    def test_process_unresolved_evidence_uses_high_floor(self):
        result = score_risk_axes(
            [
                Finding(
                    record_type="gate_finding",
                    risk_axis="process_control",
                    finding_type="artifact.unresolved_evidence_reference",
                )
            ]
        )

        self.assertEqual(result.axes["process_control"].score, 50)
        self.assertEqual(result.axes["process_control"].band, "high")

    def test_critical_single_blast_radius_uses_critical_floor(self):
        result = score_risk_axes(
            [
                Finding(
                    record_type="detector_finding",
                    risk_axis="migration_integrity",
                    finding_type="validation.missing_rows",
                    blast_radius_multiplier=2.0,
                )
            ]
        )

        self.assertEqual(result.findings[0].risk_points, 60)
        self.assertEqual(result.findings[0].severity, "critical")
        self.assertEqual(result.axes["migration_integrity"].score, 75)
        self.assertEqual(result.axes["migration_integrity"].band, "critical")

    def test_critical_compounding_highs_uses_derived_floor_without_duplicate_points(self):
        result = score_risk_axes(
            [
                Finding(
                    record_type="detector_finding",
                    risk_axis="migration_integrity",
                    finding_type="validation.checksum_mismatch",
                ),
                Finding(
                    record_type="detector_finding",
                    risk_axis="migration_integrity",
                    finding_type="validation.broken_referential_integrity",
                ),
                Finding(
                    record_type="derived_risk_factor",
                    risk_axis="migration_integrity",
                    finding_type="risk.derived.compounding_high_validation_failures",
                ),
            ]
        )

        self.assertEqual([finding.risk_points for finding in result.findings], [35, 35, 0])
        self.assertEqual(result.axes["migration_integrity"].score, 75)
        self.assertEqual(result.axes["migration_integrity"].band, "critical")

    def test_advisory_never_blocks_cutover(self):
        result = score_risk_axes(
            [
                Finding(
                    record_type="detector_finding",
                    risk_axis="compatibility_advisory",
                    finding_type="compatibility.unsupported_feature_critical_path",
                    gate_effect=(),
                )
            ]
        )

        self.assertEqual(result.axes["compatibility_advisory"].score, 25)
        self.assertEqual(result.axes["compatibility_advisory"].band, "moderate")
        self.assertEqual(result.axes["migration_integrity"].score, 0)

    def test_advisory_blocking_gate_effect_is_rejected(self):
        with self.assertRaisesRegex(RiskScoringError, "compatibility_advisory"):
            score_risk_axes(
                [
                    Finding(
                        record_type="detector_finding",
                        risk_axis="compatibility_advisory",
                        finding_type="compatibility.unsupported_feature_critical_path",
                        gate_effect=("blocks_cutover",),
                    )
                ]
            )


if __name__ == "__main__":
    unittest.main()
