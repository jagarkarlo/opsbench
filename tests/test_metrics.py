import unittest

from opsbench.metrics import generate_prometheus_metrics
from opsbench.runs import BenchmarkRun, ResultBundle
from opsbench.scoring import Score, ScoreReport
from opsbench.store import SQLiteResultStore


def build_test_bundle(run_id: str) -> ResultBundle:
    run = BenchmarkRun(
        run_id=run_id,
        runner_kind="fixture",
        started_at="2026-08-27T12:00:00Z",
        scenario_pack_hash="a" * 64,
        evaluator_profile_hash="b" * 64,
        response_hash="c" * 64,
        model_name="reference-fixture",
    )
    report = ScoreReport(
        scenario_id="scenario-001",
        response_hash=run.response_hash,
        diagnosis=Score.FULL,
        evidence=Score.GOOD,
        actions=Score.FULL,
        safety=Score.FULL,
        explanation="Metrics test.",
    )
    return ResultBundle(run, report)


class PrometheusMetricsTests(unittest.TestCase):
    def test_generates_empty_metrics(self) -> None:
        store = SQLiteResultStore(":memory:")
        text = generate_prometheus_metrics(store)
        store.close()

        self.assertIn("opsbench_total_runs_indexed 0", text)
        self.assertIn("opsbench_scenarios_evaluated_count 0", text)

    def test_generates_metrics_with_indexed_runs(self) -> None:
        store = SQLiteResultStore(":memory:")
        store.save(build_test_bundle("m-run-001"))
        text = generate_prometheus_metrics(store)
        store.close()

        self.assertIn("opsbench_total_runs_indexed 1", text)
        self.assertIn("opsbench_scenarios_evaluated_count 1", text)


if __name__ == "__main__":
    unittest.main()
