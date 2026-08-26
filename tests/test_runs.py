import unittest

from opsbench.runs import BenchmarkRun


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

    def test_rejects_invalid_timestamp_and_hashes(self) -> None:
        with self.assertRaisesRegex(ValueError, "started_at must be an ISO-8601 timestamp"):
            self.build_run(started_at="soon")
        with self.assertRaisesRegex(ValueError, "response_hash must be a SHA-256 hex digest"):
            self.build_run(response_hash="not-a-digest")


if __name__ == "__main__":
    unittest.main()