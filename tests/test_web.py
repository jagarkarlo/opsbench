import unittest

from opsbench.runs import BenchmarkRun, ResultBundle
from opsbench.scoring import Score, ScoreReport
from opsbench.store import SQLiteResultStore
from opsbench.web import render_dashboard_html


def build_test_bundle(run_id: str, scenario_id: str = "scenario-001", score: Score = Score.FULL) -> ResultBundle:
    run = BenchmarkRun(
        run_id=run_id,
        runner_kind="fixture",
        started_at="2026-08-27T12:00:00Z",
        scenario_pack_hash="a" * 64,
        evaluator_profile_hash="b" * 64,
        response_hash="c" * 64,
        model_name="gpt-4o",
    )
    report = ScoreReport(
        scenario_id=scenario_id,
        response_hash=run.response_hash,
        diagnosis=score,
        evidence=Score.GOOD,
        actions=Score.FULL,
        safety=Score.FULL,
        explanation="Dashboard test.",
    )
    return ResultBundle(run, report)


class WebDashboardTests(unittest.TestCase):
    def test_renders_empty_dashboard_html(self) -> None:
        store = SQLiteResultStore(":memory:")
        html_out = render_dashboard_html(store)
        store.close()

        self.assertIn("OpsBench Web Console", html_out)
        self.assertIn("No benchmark runs recorded yet.", html_out)

    def test_console_avoids_the_generic_dark_saas_template_look(self) -> None:
        """Locks in the hand-picked ledger theme instead of a templated AI dashboard."""
        store = SQLiteResultStore(":memory:")
        html_out = render_dashboard_html(store)
        store.close()

        for stale_token in ("#0f172a", "#38bdf8", "system-ui", 'class="card"', "metric-value"):
            self.assertNotIn(stale_token, html_out)
        self.assertIn("stat-line", html_out)

    def test_renders_dashboard_html_with_indexed_runs(self) -> None:
        store = SQLiteResultStore(":memory:")
        store.save(build_test_bundle("run-001"))
        store.save(build_test_bundle("run-002", score=Score.GOOD))

        html_out = render_dashboard_html(store)
        store.close()

        self.assertIn("OpsBench Web Console", html_out)
        self.assertIn("scenario-001", html_out)
        self.assertIn("gpt-4o", html_out)
        self.assertIn("run-001", html_out)
        self.assertIn("Portfolio Leaderboard", html_out)
        self.assertIn("Conservative Score", html_out)


if __name__ == "__main__":
    unittest.main()
