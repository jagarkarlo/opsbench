from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from opsbench.export import export_store_to_json, import_json_to_store
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
        explanation="Export test.",
    )
    return ResultBundle(run, report)


class ExportImportTests(unittest.TestCase):
    def test_exports_and_imports_result_bundles(self) -> None:
        source_store = SQLiteResultStore(":memory:")
        source_store.save(build_test_bundle("exp-run-001"))
        source_store.save(build_test_bundle("exp-run-002"))

        with TemporaryDirectory() as tmpdir:
            export_file = Path(tmpdir) / "export.json"

            exported_count = export_store_to_json(source_store, export_file)
            self.assertEqual(exported_count, 2)
            self.assertTrue(export_file.is_file())

            target_store = SQLiteResultStore(":memory:")
            imported_count = import_json_to_store(target_store, export_file)
            self.assertEqual(imported_count, 2)

            retrieved = target_store.get("exp-run-001")
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.run.run_id, "exp-run-001")

            target_store.close()

        source_store.close()

    def test_rejects_invalid_export_version(self) -> None:
        store = SQLiteResultStore(":memory:")
        with TemporaryDirectory() as tmpdir:
            invalid_file = Path(tmpdir) / "invalid.json"
            invalid_file.write_text('{"export_version": "9.9", "bundles": []}', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "unsupported or missing export_version"):
                import_json_to_store(store, invalid_file)
        store.close()


if __name__ == "__main__":
    unittest.main()
