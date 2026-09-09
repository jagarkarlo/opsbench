import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from opsbench.verification import (
    MONITORING_STAGE_IDS,
    STAGE_STATUSES,
    VerificationAssertion,
    VerificationInput,
    VerificationObservation,
    evaluate_verification,
    load_verification_input,
    load_verification_report,
    write_verification_report,
)


def build_input(*statuses: str) -> VerificationInput:
    observations = tuple(
        VerificationObservation(
            stage_id=stage_id,
            status=status,
            observed_at=f"2026-09-09T12:0{index}:00Z",
            evidence_refs=(f"evidence-{index}",),
            summary=f"Synthetic observation for {stage_id}.",
        )
        for index, (stage_id, status) in enumerate(zip(MONITORING_STAGE_IDS, statuses), start=1)
    )
    assertions = tuple(
        VerificationAssertion(
            assertion_id=f"assert-{stage_id}",
            stage_id=stage_id,
            description=f"{stage_id} must be observed.",
        )
        for stage_id in MONITORING_STAGE_IDS
    )
    return VerificationInput(
        verification_id="verification-001",
        scenario_id="monitoring-path-001",
        started_at="2026-09-09T12:00:00Z",
        assertions=assertions,
        observations=observations,
    )


class VerificationContractTests(unittest.TestCase):
    def test_healthy_path_is_passed_with_complete_coverage(self) -> None:
        result = evaluate_verification(build_input(*(["passed"] * len(MONITORING_STAGE_IDS))))

        self.assertEqual(result.outcome, "passed")
        self.assertEqual(result.coverage.tested_stage_count, len(MONITORING_STAGE_IDS))
        self.assertEqual(result.coverage.total_stage_count, len(MONITORING_STAGE_IDS))
        self.assertEqual(result.coverage.ratio, 1.0)
        self.assertTrue(all(assertion.status == "passed" for assertion in result.assertions))

    def test_failed_stage_wins_without_inventing_a_root_cause(self) -> None:
        statuses = ["passed"] * len(MONITORING_STAGE_IDS)
        statuses[2] = "failed"
        result = evaluate_verification(build_input(*statuses))

        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.assertions[2].status, "failed")
        self.assertIn("Synthetic observation", result.observations[2].summary)
        self.assertNotIn("root_cause", result.to_dict())

    def test_unknown_and_not_tested_are_retained_as_partial_coverage(self) -> None:
        statuses = ["passed", "unknown", "not_tested", "passed", "passed"]
        result = evaluate_verification(build_input(*statuses))

        self.assertEqual(result.outcome, "unknown")
        self.assertEqual(result.coverage.tested_stage_count, 4)
        self.assertEqual(result.coverage.total_stage_count, 5)
        self.assertEqual(result.coverage.ratio, 0.8)
        self.assertEqual(result.assertions[1].status, "unknown")
        self.assertEqual(result.assertions[2].status, "not_tested")

    def test_contract_rejects_duplicate_or_unknown_stages(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate stage_id"):
            VerificationInput(
                verification_id="verification-001",
                scenario_id="monitoring-path-001",
                started_at="2026-09-09T12:00:00Z",
                assertions=(),
                observations=(
                    VerificationObservation("signal_emitted", "passed"),
                    VerificationObservation("signal_emitted", "passed"),
                ),
            )
        with self.assertRaisesRegex(ValueError, "unsupported stage_id"):
            VerificationObservation("made_up_stage", "passed")
        with self.assertRaisesRegex(ValueError, "unsupported status"):
            VerificationObservation("signal_emitted", "green")

    def test_report_round_trips_through_bounded_json(self) -> None:
        with TemporaryDirectory() as directory:
            input_path = Path(directory) / "verification-input.json"
            report_path = Path(directory) / "verification.json"
            verification_input = build_input(*(["passed"] * len(MONITORING_STAGE_IDS)))
            report = evaluate_verification(build_input(*(["passed"] * len(MONITORING_STAGE_IDS))))
            write_verification_report(report_path, report)
            decoded = json.loads(report_path.read_text(encoding="utf-8"))
            loaded_report = load_verification_report(report_path)
            input_path.write_text(json.dumps(verification_input.to_dict()), encoding="utf-8")
            loaded_input = load_verification_input(input_path)

        self.assertEqual(decoded["schema_version"], "1.0")
        self.assertEqual(decoded["outcome"], "passed")
        self.assertEqual(len(decoded["observations"]), len(MONITORING_STAGE_IDS))
        self.assertEqual({"passed"}, {item["status"] for item in decoded["observations"]})
        self.assertEqual(STAGE_STATUSES, frozenset({"passed", "failed", "unknown", "not_tested"}))
        self.assertEqual(verification_input, loaded_input)
        self.assertEqual(report.content_hash(), loaded_report.content_hash())


if __name__ == "__main__":
    unittest.main()