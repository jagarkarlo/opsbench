from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from opsbench.recovery import run_recovery_drill, run_recovery_drill_series
from opsbench.runs import BenchmarkRun, ResultBundle
from opsbench.scoring import Score, ScoreReport
from opsbench.store import SQLiteResultStore


def build_bundle(run_id: str) -> ResultBundle:
    response_hash = ("a" if run_id == "run-001" else "b") * 64
    return ResultBundle(
        BenchmarkRun(
            run_id=run_id,
            runner_kind="fixture",
            started_at="2026-09-03T12:00:00Z",
            scenario_pack_hash="c" * 64,
            evaluator_profile_hash="d" * 64,
            response_hash=response_hash,
            model_name="test-model",
        ),
        ScoreReport(
            scenario_id="scenario-001",
            response_hash=response_hash,
            diagnosis=Score.GOOD,
            evidence=Score.FULL,
            actions=Score.LOW,
            safety=Score.FULL,
            explanation="synthetic recovery drill result",
        ),
    )


class RecoveryDrillTests(unittest.TestCase):
    def test_exports_restores_and_verifies_bundle_hashes(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source_database = directory / "source.db"
            source_store = SQLiteResultStore(source_database)
            try:
                source_store.save(build_bundle("run-001"))
                source_store.save(build_bundle("run-002"))
            finally:
                source_store.close()

            result = run_recovery_drill(
                source_database,
                directory / "backup.json",
                directory / "restored.db",
            )

            self.assertEqual(result.source_count, 2)
            self.assertEqual(result.restored_count, 2)
            self.assertEqual(len(result.restored_bundle_hashes), 2)
            self.assertTrue((directory / "backup.json").is_file())
            self.assertTrue((directory / "restored.db").is_file())
            self.assertEqual(result.to_dict()["status"], "verified")

    def test_rejects_existing_restore_database(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source_database = directory / "source.db"
            source_store = SQLiteResultStore(source_database)
            source_store.close()
            restored_database = directory / "restored.db"
            restored_database.touch()

            with self.assertRaisesRegex(ValueError, "must not already exist"):
                run_recovery_drill(source_database, directory / "backup.json", restored_database)

    def test_runs_recovery_series_with_bounded_retention(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source_database = directory / "source.db"
            source_store = SQLiteResultStore(source_database)
            source_store.save(build_bundle("run-001"))
            source_store.close()

            result = run_recovery_drill_series(
                source_database,
                directory / "drills",
                attempts=3,
                retention=2,
            )

            self.assertEqual(result.to_dict()["status"], "verified")
            self.assertEqual(result.retained_attempts, 2)
            self.assertEqual(result.removed_attempts, 1)
            self.assertEqual(result.attempts[2].archive_path.split("/")[-2], "attempt-0003")
            self.assertFalse((directory / "drills" / "attempt-0001").exists())
            self.assertTrue((directory / "drills" / "attempt-0002" / "backup.json").is_file())
            self.assertTrue((directory / "drills" / "attempt-0003" / "restored.db").is_file())

    def test_rejects_retention_greater_than_attempts(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            with self.assertRaisesRegex(ValueError, "must not exceed"):
                run_recovery_drill_series(
                    Path(temporary_directory) / "source.db",
                    Path(temporary_directory) / "drills",
                    attempts=1,
                    retention=2,
                )


if __name__ == "__main__":
    unittest.main()
