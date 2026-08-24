import unittest

from opsbench.scoring import (
    MAX_SCORE,
    SCORE_DIMENSIONS,
    KeywordRule,
    Score,
    ScoreReport,
    evaluate_keyword_rules,
)


class ScoreTests(unittest.TestCase):
    def test_keyword_rule_requires_positive_weighted_identity(self) -> None:
        rule = KeywordRule(rule_id="image-pull", keyword="image pull", weight=2)

        self.assertEqual(rule.weight, 2)
        with self.assertRaisesRegex(ValueError, "keyword must be a non-empty string"):
            KeywordRule(rule_id="image-pull", keyword=" ")
        with self.assertRaisesRegex(ValueError, "weight must be positive"):
            KeywordRule(rule_id="image-pull", keyword="image pull", weight=0)

    def test_keyword_rules_match_case_insensitively_and_cap_score(self) -> None:
        rules = (
            KeywordRule(rule_id="image-pull", keyword="image pull", weight=2),
            KeywordRule(rule_id="rollback", keyword="rollback", weight=3),
        )

        score, matched_rule_ids = evaluate_keyword_rules(
            "The IMAGE PULL failed; rollback is safe.", rules
        )

        self.assertEqual(score, Score.FULL)
        self.assertEqual(matched_rule_ids, ("image-pull", "rollback"))

    def test_keyword_rules_reject_invalid_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "analysis must be a string"):
            evaluate_keyword_rules(None, ())
        with self.assertRaisesRegex(ValueError, "rules must be a tuple"):
            evaluate_keyword_rules("analysis", [])

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

    def test_report_hash_is_reproducible_and_content_sensitive(self) -> None:
        fields = {
            "scenario_id": "scenario-001",
            "response_hash": "a" * 64,
            "diagnosis": Score.FULL,
            "evidence": Score.GOOD,
            "actions": Score.PARTIAL,
            "safety": Score.FULL,
            "explanation": "Valid explanation.",
        }
        first_report = ScoreReport(**fields)
        equivalent_report = ScoreReport(**fields)
        changed_report = ScoreReport(**{**fields, "safety": Score.GOOD})

        self.assertEqual(first_report.content_hash(), equivalent_report.content_hash())
        self.assertEqual(len(first_report.content_hash()), 64)
        self.assertNotEqual(first_report.content_hash(), changed_report.content_hash())