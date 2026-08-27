from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from opsbench.runs import BenchmarkRun, ResultBundle
from opsbench.scoring import Score, ScoreReport
from opsbench.store import RunQuery, SQLiteResultStore


def build_test_bundle(
    run_id: str,
    scenario_id: str = "scenario-001",
    runner_kind: str = "fixture",
    model_name: str = "reference-fixture",
    diagnosis: Score = Score.FULL,
) -> ResultBundle:
    run = BenchmarkRun(
        run_id=run_id,
        runner_kind=runner_kind,
        started_at="2026-08-27T12:00:00Z",
        scenario_pack_hash="a" * 64,
        evaluator_profile_hash="b" * 64,
        response_hash="c" * 64,
        model_name=model_name,
    )
    report = ScoreReport(
        scenario_id=scenario_id,
        response_hash=run.response_hash,
        diagnosis=diagnosis,
        evidence=Score.GOOD,
        actions=Score.FULL,
        safety=Score.FULL,
        explanation="Test explanation.",
    )
    return ResultBundle(run, report)


class SQLiteResultStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = SQLiteResultStore(":memory:")

    def tearDown(self) -> None:
        self.store.close()

    def test_saves_and_retrieves_result_bundle(self) -> None:
        bundle = build_test_bundle("run-001")
        self.store.save(bundle)

        retrieved = self.store.get("run-001")

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.content_hash(), bundle.content_hash())
        self.assertEqual(self.store.count(), 1)

    def test_returns_none_for_missing_run_id(self) -> None:
        self.assertIsNone(self.store.get("non-existent"))

    def test_rejects_duplicate_run_id(self) -> None:
        bundle = build_test_bundle("run-001")
        self.store.save(bundle)

        with self.assertRaisesRegex(ValueError, "already exists in store"):
            self.store.save(bundle)

    def test_queries_by_scenario_id_and_model_name(self) -> None:
        self.store.save(build_test_bundle("run-001", scenario_id="scenario-001", model_name="gpt-4o"))
        self.store.save(build_test_bundle("run-002", scenario_id="scenario-002", model_name="llama3"))
        self.store.save(build_test_bundle("run-003", scenario_id="scenario-001", model_name="llama3"))

        all_sc1 = self.store.query(RunQuery(scenario_id="scenario-001"))
        self.assertEqual(len(all_sc1), 2)

        gpt_sc1 = self.store.query(RunQuery(scenario_id="scenario-001", model_name="gpt-4o"))
        self.assertEqual(len(gpt_sc1), 1)
        self.assertEqual(gpt_sc1[0].run.run_id, "run-001")

    def test_persists_to_disk_file(self) -> None:
        with TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "benchmarks.db"
            disk_store = SQLiteResultStore(db_file)
            bundle = build_test_bundle("run-disk-001")
            disk_store.save(bundle)
            disk_store.close()

            reopened_store = SQLiteResultStore(db_file)
            retrieved = reopened_store.get("run-disk-001")
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.content_hash(), bundle.content_hash())
            reopened_store.close()


if __name__ == "__main__":
    unittest.main()
