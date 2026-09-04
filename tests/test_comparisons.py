import unittest

from opsbench.comparisons import (
    compare_bundles,
    rank_portfolio,
    render_markdown_comparison,
    rank_trials,
    summarize_portfolio,
    summarize_trials,
)
from opsbench.runs import BenchmarkRun, ResultBundle
from opsbench.scoring import Score, ScoreReport


def build_bundle(*, run_id: str, model_name: str, total_score: Score) -> ResultBundle:
    run = BenchmarkRun(
        run_id=run_id,
        runner_kind="fixture",
        started_at="2026-08-26T12:00:00Z",
        scenario_pack_hash="a" * 64,
        evaluator_profile_hash="b" * 64,
        response_hash=("c" if run_id == "run-001" else "d") * 64,
        model_name=model_name,
    )
    report = ScoreReport(
        scenario_id="scenario-001",
        response_hash=run.response_hash,
        diagnosis=total_score,
        evidence=Score.ZERO,
        actions=Score.ZERO,
        safety=Score.ZERO,
        explanation="Synthetic result.",
    )
    return ResultBundle(run, report)


class ComparisonTests(unittest.TestCase):
    def test_summarizes_same_scenario_results_by_runner(self) -> None:
        summary = compare_bundles(
            (
                build_bundle(run_id="run-001", model_name="fixture-alpha", total_score=Score.FULL),
                build_bundle(run_id="run-002", model_name="fixture-beta", total_score=Score.GOOD),
            )
        )

        self.assertEqual(summary.scenario_id, "scenario-001")
        self.assertEqual(summary.runner_totals, (("fixture-alpha", 4), ("fixture-beta", 3)))

    def test_rejects_empty_or_cross_scenario_comparisons(self) -> None:
        with self.assertRaisesRegex(ValueError, "bundles must be a non-empty"):
            compare_bundles(())

        second_bundle = build_bundle(
            run_id="run-002", model_name="fixture-beta", total_score=Score.GOOD
        )
        cross_scenario_report = ScoreReport(
            scenario_id="other-scenario",
            response_hash=second_bundle.run.response_hash,
            diagnosis=Score.GOOD,
            evidence=Score.ZERO,
            actions=Score.ZERO,
            safety=Score.ZERO,
            explanation="Synthetic result.",
        )
        cross_scenario_bundle = ResultBundle(second_bundle.run, cross_scenario_report)

        with self.assertRaisesRegex(ValueError, "all bundles must belong to the same scenario"):
            compare_bundles((build_bundle(run_id="run-001", model_name="fixture-alpha", total_score=Score.FULL), cross_scenario_bundle))

    def test_summarizes_repeated_trials_by_runner(self) -> None:
        statistics = summarize_trials(
            (
                build_bundle(run_id="run-001", model_name="fixture-alpha", total_score=Score.FULL),
                build_bundle(run_id="run-002", model_name="fixture-alpha", total_score=Score.GOOD),
            )
        )

        self.assertEqual(len(statistics), 1)
        self.assertEqual(statistics[0].runner_name, "fixture-alpha")
        self.assertEqual(statistics[0].trial_count, 2)
        self.assertEqual(statistics[0].total_score, 7)
        self.assertEqual(statistics[0].average_score, 3.5)
        self.assertAlmostEqual(statistics[0].variance, 0.5)
        self.assertAlmostEqual(statistics[0].standard_deviation, 0.70710678)
        self.assertAlmostEqual(statistics[0].confidence_interval_95[0], 2.5199, places=3)
        self.assertAlmostEqual(statistics[0].confidence_interval_95[1], 4.4801, places=3)

    def test_single_trial_has_zero_uncertainty(self) -> None:
        statistics = summarize_trials(
            (build_bundle(run_id="run-001", model_name="fixture-alpha", total_score=Score.FULL),)
        )

        self.assertEqual(statistics[0].variance, 0.0)
        self.assertEqual(statistics[0].standard_deviation, 0.0)
        self.assertEqual(statistics[0].confidence_interval_95, (4.0, 4.0))

    def test_ranks_by_conservative_score_before_mean(self) -> None:
        bundles = (
            build_bundle(run_id="run-001", model_name="steady", total_score=Score.GOOD),
            build_bundle(run_id="run-002", model_name="uncertain", total_score=Score.FULL),
        )

        ranked = rank_trials(bundles)

        self.assertEqual([statistic.runner_name for statistic in ranked], ["uncertain", "steady"])
        self.assertEqual(ranked[0].conservative_score, 4.0)

    def test_renders_markdown_comparison_report(self) -> None:
        report = render_markdown_comparison(
            (
                build_bundle(run_id="run-001", model_name="fixture-alpha", total_score=Score.FULL),
                build_bundle(run_id="run-002", model_name="fixture-alpha", total_score=Score.GOOD),
            )
        )

        self.assertIn("# OpsBench Comparison Report", report)
        self.assertIn("**Scenario**: `scenario-001`", report)
        self.assertIn("| Runner | Trials | Total Score | Average Score | Std. Dev. | 95% CI |", report)
        self.assertIn("| fixture-alpha | 2 | 7 | 3.50 | 0.71 | [2.52, 4.48] |", report)

    def test_summarizes_and_ranks_multiple_scenarios_by_normalized_score(self) -> None:
        first = build_bundle(run_id="run-001", model_name="fixture-alpha", total_score=Score.FULL)
        second = build_bundle(run_id="run-002", model_name="fixture-alpha", total_score=Score.GOOD)
        other_report = ScoreReport(
            scenario_id="scenario-002",
            response_hash=second.run.response_hash,
            diagnosis=Score.FULL,
            evidence=Score.ZERO,
            actions=Score.ZERO,
            safety=Score.ZERO,
            explanation="Synthetic result.",
        )
        other = ResultBundle(second.run, other_report)

        statistics = summarize_portfolio((first, other))
        ranked = rank_portfolio((first, other))

        self.assertEqual(statistics[0].scenario_count, 2)
        self.assertEqual(statistics[0].trial_count, 2)
        self.assertEqual(statistics[0].average_score, 0.25)
        self.assertEqual(ranked[0].runner_name, "fixture-alpha")


if __name__ == "__main__":
    unittest.main()