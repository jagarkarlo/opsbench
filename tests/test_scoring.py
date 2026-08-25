import unittest

from opsbench.scoring import (
    MAX_SCORE,
    SCORE_DIMENSIONS,
    KeywordRule,
    EvaluatorProfile,
    Score,
    ScoreReport,
    evaluate_actions,
    evaluate_citations,
    evaluate_keyword_rules,
)
from opsbench.responses import BenchmarkResponse
from opsbench.scenarios import EvidenceArtifact, ScenarioManifest, ScenarioPack


class ScoreTests(unittest.TestCase):
    def test_actions_score_profile_approved_actions_case_insensitively(self) -> None:
        profile = EvaluatorProfile(
            scenario_id="kubernetes-image-reference-001",
            diagnosis_rules=(KeywordRule("image-pull", "image pull"),),
            permitted_actions=("correct image reference", "verify image tag"),
        )
        response = BenchmarkResponse(
            scenario_id="kubernetes-image-reference-001",
            analysis="The image reference should be corrected.",
            proposed_actions=("Correct Image Reference", "delete all workloads", "verify image tag"),
        )

        score, unrecognized_actions = evaluate_actions(profile, response)

        self.assertEqual(score, Score.PARTIAL)
        self.assertEqual(unrecognized_actions, ("delete all workloads",))

    def test_actions_reject_mismatched_scenario_or_invalid_contracts(self) -> None:
        profile = EvaluatorProfile(
            scenario_id="scenario-001",
            diagnosis_rules=(KeywordRule("rule", "keyword"),),
        )
        response = BenchmarkResponse("other-scenario", "Synthetic analysis")

        with self.assertRaisesRegex(ValueError, "response scenario_id must match"):
            evaluate_actions(profile, response)
        with self.assertRaisesRegex(ValueError, "profile must be an EvaluatorProfile"):
            evaluate_actions("invalid", response)

    def test_citations_score_declared_artifacts_without_reading_content(self) -> None:
        pack = ScenarioPack(
            ScenarioManifest(
                scenario_id="kubernetes-image-reference-001",
                title="Diagnose a fictional image reference failure",
                category="kubernetes",
            ),
            (
                EvidenceArtifact("deployment.yaml", "application/yaml", b"private-like bytes"),
                EvidenceArtifact("pod-events.json", "application/json", b"event bytes"),
            ),
        )
        response = BenchmarkResponse(
            scenario_id="kubernetes-image-reference-001",
            analysis="The image reference should be corrected.",
            cited_artifact_ids=("deployment.yaml", "missing.txt", "pod-events.json"),
        )

        score, missing_ids = evaluate_citations(pack, response)

        self.assertEqual(score, Score.PARTIAL)
        self.assertEqual(missing_ids, ("missing.txt",))

    def test_citations_reject_mismatched_scenario_or_invalid_contracts(self) -> None:
        pack = ScenarioPack(
            ScenarioManifest("scenario-001", "Fictional scenario", "kubernetes"),
            (EvidenceArtifact("logs.txt", "text/plain", b"synthetic logs"),),
        )
        response = BenchmarkResponse("other-scenario", "Synthetic analysis")

        with self.assertRaisesRegex(ValueError, "response scenario_id must match"):
            evaluate_citations(pack, response)
        with self.assertRaisesRegex(ValueError, "pack must be a ScenarioPack"):
            evaluate_citations("invalid", response)

    def test_evaluator_profile_requires_unique_rules_and_actions(self) -> None:
        image_rule = KeywordRule("image-pull", "image pull", weight=2)
        profile = EvaluatorProfile(
            scenario_id="kubernetes-image-reference-001",
            diagnosis_rules=(image_rule,),
            permitted_actions=("correct image reference",),
        )

        self.assertEqual(profile.scenario_id, "kubernetes-image-reference-001")
        with self.assertRaisesRegex(ValueError, "diagnosis_rules must not be empty"):
            EvaluatorProfile("scenario-001", ())
        with self.assertRaisesRegex(ValueError, "diagnosis rule IDs must be unique"):
            EvaluatorProfile("scenario-001", (image_rule, image_rule))
        with self.assertRaisesRegex(ValueError, "permitted_actions must be unique"):
            EvaluatorProfile(
                "scenario-001",
                (image_rule,),
                ("correct image reference", "correct image reference"),
            )

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