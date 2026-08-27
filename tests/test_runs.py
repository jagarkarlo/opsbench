import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from opsbench.runs import BenchmarkRun, ResultBundle, load_result_bundle, write_result_bundle
from opsbench.scoring import Score, ScoreReport


class BenchmarkRunTests(unittest.TestCase):
    def build_run(self, **overrides: str | None) -> BenchmarkRun:
        fields = {
            "run_id": "fixture-run-001",
            "runner_kind": "fixture",
            "started_at": "2026-08-26T12:00:00Z",
            "scenario_pack_hash": "a" * 64,
            "evaluator_profile_hash": "b" * 64,
            "response_hash": "c" * 64,
            "model_name": "reference-fixture",
        }
        fields.update(overrides)
        return BenchmarkRun(**fields)

    def test_has_reproducible_identity(self) -> None:
        first_run = self.build_run()
        equivalent_run = self.build_run()
        changed_run = self.build_run(run_id="fixture-run-002")

        self.assertEqual(first_run.content_hash(), equivalent_run.content_hash())
        self.assertNotEqual(first_run.content_hash(), changed_run.content_hash())

    def test_canonicalizes_metadata_and_includes_it_in_identity(self) -> None:
        run = self.build_run(metadata=(("temperature", "0"), ("seed", "42")))
        changed_run = self.build_run(metadata=(("seed", "43"), ("temperature", "0")))

        self.assertEqual(run.to_dict()["metadata"], {"seed": "42", "temperature": "0"})
        self.assertNotEqual(run.content_hash(), changed_run.content_hash())

    def test_rejects_invalid_or_duplicate_metadata(self) -> None:
        with self.assertRaisesRegex(ValueError, "metadata keys must be unique"):
            self.build_run(metadata=(("seed", "42"), ("seed", "43")))
        with self.assertRaisesRegex(ValueError, "metadata must be a tuple"):
            self.build_run(metadata=(("", "42"),))

    def test_rejects_invalid_timestamp_and_hashes(self) -> None:
        with self.assertRaisesRegex(ValueError, "started_at must be an ISO-8601 timestamp"):
            self.build_run(started_at="soon")
        with self.assertRaisesRegex(ValueError, "response_hash must be a SHA-256 hex digest"):
            self.build_run(response_hash="not-a-digest")

    def test_result_bundle_has_reproducible_identity(self) -> None:
        run = self.build_run()
        report = ScoreReport(
            scenario_id="scenario-001",
            response_hash=run.response_hash,
            diagnosis=Score.PARTIAL,
            evidence=Score.GOOD,
            actions=Score.FULL,
            safety=Score.FULL,
            explanation="Synthetic deterministic result.",
        )
        first_bundle = ResultBundle(run, report)
        equivalent_bundle = ResultBundle(run, report)

        self.assertEqual(first_bundle.content_hash(), equivalent_bundle.content_hash())
        self.assertEqual(first_bundle.to_dict()["run"]["run_id"], "fixture-run-001")

    def test_result_bundle_rejects_mismatched_response(self) -> None:
        run = self.build_run()
        report = ScoreReport(
            scenario_id="scenario-001",
            response_hash="d" * 64,
            diagnosis=Score.ZERO,
            evidence=Score.ZERO,
            actions=Score.ZERO,
            safety=Score.FULL,
            explanation="Synthetic deterministic result.",
        )

        with self.assertRaisesRegex(ValueError, "run response_hash must match"):
            ResultBundle(run, report)

    def test_writes_canonical_bundle_without_overwriting(self) -> None:
        run = self.build_run()
        report = ScoreReport(
            scenario_id="scenario-001",
            response_hash=run.response_hash,
            diagnosis=Score.PARTIAL,
            evidence=Score.GOOD,
            actions=Score.FULL,
            safety=Score.FULL,
            explanation="Synthetic deterministic result.",
        )
        bundle = ResultBundle(run, report)
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "nested" / "result.json"

            write_result_bundle(path, bundle)

            self.assertEqual(path.read_text(encoding="utf-8"), bundle.canonical_json() + "\n")
            with self.assertRaisesRegex(ValueError, "result bundle already exists"):
                write_result_bundle(path, bundle)

    def test_loads_written_result_bundle(self) -> None:
        run = self.build_run()
        report = ScoreReport(
            scenario_id="scenario-001",
            response_hash=run.response_hash,
            diagnosis=Score.PARTIAL,
            evidence=Score.GOOD,
            actions=Score.FULL,
            safety=Score.FULL,
            explanation="Synthetic deterministic result.",
        )
        expected_bundle = ResultBundle(run, report)
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "result.json"
            write_result_bundle(path, expected_bundle)

            bundle = load_result_bundle(path)

        self.assertEqual(bundle.content_hash(), expected_bundle.content_hash())

    def test_rejects_invalid_result_bundle_shape(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "result.json"
            path.write_text('{"run":{}}', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "exactly run and report"):
                load_result_bundle(path)


if __name__ == "__main__":
    unittest.main()