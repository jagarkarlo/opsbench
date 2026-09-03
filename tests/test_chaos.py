from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from opsbench.chaos import run_chaos_matrix
from opsbench.failure_injection import FailureMode


def write_scenario_gallery(gallery: Path) -> None:
    scenario = gallery / "alpha"
    responses = scenario / "responses"
    responses.mkdir(parents=True)
    (scenario / "scenario.json").write_text(
        '{"manifest":{"schema_version":"1.0","scenario_id":"scenario-001","title":"Test","category":"kubernetes"},"evidence":[{"artifact_id":"logs.txt","media_type":"text/plain","relative_path":"logs.txt"}]}',
        encoding="utf-8",
    )
    (scenario / "logs.txt").write_text("synthetic logs\n", encoding="utf-8")
    (scenario / "evaluator.json").write_text(
        '{"scenario_id":"scenario-001","diagnosis_rules":[{"rule_id":"synthetic","keyword":"synthetic","weight":1}]}',
        encoding="utf-8",
    )
    (responses / "reference-response.json").write_text(
        '{"scenario_id":"scenario-001","analysis":"Synthetic analysis."}',
        encoding="utf-8",
    )


class ChaosMatrixTests(unittest.TestCase):
    def test_runs_bounded_matrix_in_deterministic_case_order(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            gallery = directory / "gallery"
            write_scenario_gallery(gallery)

            result = run_chaos_matrix(
                gallery,
                directory / "matrix",
                iterations=2,
                modes=(FailureMode.TIMEOUT, FailureMode.MISSING_EVIDENCE),
            )

            self.assertEqual(result.to_dict()["case_count"], 4)
            self.assertEqual(result.failure_count, 2)
            self.assertEqual(
                [(case.iteration, case.mode) for case in result.cases],
                [
                    (1, FailureMode.TIMEOUT),
                    (1, FailureMode.MISSING_EVIDENCE),
                    (2, FailureMode.TIMEOUT),
                    (2, FailureMode.MISSING_EVIDENCE),
                ],
            )
            self.assertTrue((directory / "matrix" / "iteration-0002" / "timeout").is_dir())

    def test_rejects_existing_matrix_case_output(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            gallery = directory / "gallery"
            write_scenario_gallery(gallery)
            output_directory = directory / "matrix"
            (output_directory / "iteration-0001" / "timeout").mkdir(parents=True)

            with self.assertRaisesRegex(ValueError, "output already exists"):
                run_chaos_matrix(
                    gallery,
                    output_directory,
                    iterations=1,
                    modes=(FailureMode.TIMEOUT,),
                )


if __name__ == "__main__":
    unittest.main()