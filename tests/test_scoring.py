import unittest

from opsbench.scoring import MAX_SCORE, SCORE_DIMENSIONS, Score, ScoreReport


class ScoreTests(unittest.TestCase):
    def test_score_scale_is_bounded_and_ordered(self) -> None:
        self.assertEqual(int(Score.ZERO), 0)
        self.assertEqual(int(Score.FULL), MAX_SCORE)
        self.assertLess(Score.PARTIAL, Score.GOOD)

    def test_dimensions_are_explicit_and_stable(self) -> None:
        self.assertEqual(
            SCORE_DIMENSIONS,
            ("diagnosis", "evidence", "actions", "safety"),
        )

    def test_report_calculates_total_and_serializes_scores(self) -> None:
        report = ScoreReport(
            scenario_id="scenario-001",
            response_hash="a" * 64,
            diagnosis=Score.FULL,
            evidence=Score.GOOD,
            actions=Score.PARTIAL,
            safety=Score.FULL,
            explanation="The response identified the failure and proposed a safe action.",
        )

        self.assertEqual(report.total, 13)
        self.assertEqual(report.maximum, 16)
        self.assertEqual(report.to_dict()["diagnosis"], 4)

    def test_report_rejects_invalid_identity_or_scores(self) -> None:
        fields = {
            "scenario_id": "scenario-001",
            "response_hash": "a" * 64,
            "diagnosis": Score.FULL,
            "evidence": Score.GOOD,
            "actions": Score.PARTIAL,
            "safety": Score.FULL,
            "explanation": "Valid explanation.",
        }

        with self.assertRaisesRegex(ValueError, "response_hash must not be empty"):
            ScoreReport(**{**fields, "response_hash": " "})
        with self.assertRaisesRegex(ValueError, "diagnosis must be a Score"):
            ScoreReport(**{**fields, "diagnosis": 4})