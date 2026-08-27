from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from opsbench.responses import (
    BenchmarkResponse,
    SUPPORTED_RESPONSE_VERSION,
    load_response,
    parse_response_text,
)


class BenchmarkResponseTests(unittest.TestCase):
    def test_accepts_a_normalized_response(self) -> None:
        response = BenchmarkResponse(
            scenario_id="kubernetes-crashloop-001",
            analysis="The deployment references an unavailable image.",
            cited_artifact_ids=("deployment.yaml",),
            proposed_actions=("rollback deployment",),
            model_name="fixture-model",
            adapter_name="fixture",
        )

        self.assertEqual(response.response_version, SUPPORTED_RESPONSE_VERSION)
        self.assertEqual(response.cited_artifact_ids, ("deployment.yaml",))

    def test_rejects_empty_identity_and_analysis(self) -> None:
        with self.assertRaisesRegex(ValueError, "scenario_id must not be empty"):
            BenchmarkResponse(scenario_id=" ", analysis="Valid analysis")

        with self.assertRaisesRegex(ValueError, "analysis must not be empty"):
            BenchmarkResponse(scenario_id="scenario-001", analysis=" ")

    def test_rejects_invalid_version_and_field_types(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported response_version"):
            BenchmarkResponse(
                scenario_id="scenario-001",
                analysis="Valid analysis",
                response_version="2.0",
            )

        with self.assertRaisesRegex(ValueError, "proposed_actions must be a tuple of strings"):
            BenchmarkResponse(
                scenario_id="scenario-001",
                analysis="Valid analysis",
                proposed_actions=["rollback"],
            )

    def test_rejects_duplicate_or_empty_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "cited_artifact_ids must be unique"):
            BenchmarkResponse(
                scenario_id="scenario-001",
                analysis="Valid analysis",
                cited_artifact_ids=("logs.txt", "logs.txt"),
            )

        with self.assertRaisesRegex(ValueError, "proposed_actions must not contain empty values"):
            BenchmarkResponse(
                scenario_id="scenario-001",
                analysis="Valid analysis",
                proposed_actions=(" ",),
            )

    def test_serializes_schema_fields_in_stable_json(self) -> None:
        response = BenchmarkResponse(
            scenario_id="scenario-001",
            analysis="The database is saturated.",
            cited_artifact_ids=("metrics.json",),
            proposed_actions=("scale readers",),
            model_name="fixture-model",
            adapter_name="fixture",
        )

        self.assertEqual(
            response.canonical_json(),
            '{"adapter_name":"fixture","analysis":"The database is saturated.",'
            '"cited_artifact_ids":["metrics.json"],"model_name":"fixture-model",'
            '"proposed_actions":["scale readers"],"response_version":"1.0",'
            '"scenario_id":"scenario-001"}',
        )

    def test_hash_is_reproducible_and_changes_with_content(self) -> None:
        response = BenchmarkResponse(
            scenario_id="scenario-001",
            analysis="The database is saturated.",
            cited_artifact_ids=("metrics.json",),
        )
        equivalent_response = BenchmarkResponse(
            scenario_id="scenario-001",
            analysis="The database is saturated.",
            cited_artifact_ids=("metrics.json",),
        )
        changed_response = BenchmarkResponse(
            scenario_id="scenario-001",
            analysis="The database is healthy.",
            cited_artifact_ids=("metrics.json",),
        )

        self.assertEqual(response.content_hash(), equivalent_response.content_hash())
        self.assertEqual(len(response.content_hash()), 64)
        self.assertNotEqual(response.content_hash(), changed_response.content_hash())


class LoadResponseTests(unittest.TestCase):
    def write_response(self, directory: Path, content: str) -> Path:
        path = directory / "response.json"
        path.write_text(content, encoding="utf-8")
        return path

    def test_loads_json_arrays_into_normalized_tuples(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            path = self.write_response(
                Path(temporary_directory),
                '{"scenario_id":"scenario-001","analysis":"Healthy.",'
                '"cited_artifact_ids":["metrics.json"],"proposed_actions":[]}',
            )

            response = load_response(path)

        self.assertEqual(response.cited_artifact_ids, ("metrics.json",))
        self.assertEqual(response.proposed_actions, ())

    def test_rejects_invalid_shape_and_fields(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            invalid_path = self.write_response(directory, "[]")
            with self.assertRaisesRegex(ValueError, "response root must be a JSON object"):
                load_response(invalid_path)

            missing_path = self.write_response(directory, '{"scenario_id":"scenario-001"}')
            with self.assertRaisesRegex(ValueError, "response is missing fields"):
                load_response(missing_path)

            unknown_path = self.write_response(
                directory,
                '{"scenario_id":"scenario-001","analysis":"Healthy.","score":1}',
            )
            with self.assertRaisesRegex(ValueError, "response has unknown fields"):
                load_response(unknown_path)

    def test_rejects_invalid_json_arrays_and_oversized_files(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            invalid_json_path = self.write_response(directory, "not-json")
            with self.assertRaisesRegex(ValueError, "response text is not valid JSON"):
                load_response(invalid_json_path)

            invalid_array_path = self.write_response(
                directory,
                '{"scenario_id":"scenario-001","analysis":"Healthy.","proposed_actions":"none"}',
            )
            with self.assertRaisesRegex(ValueError, "proposed_actions must be a JSON array"):
                load_response(invalid_array_path)

    def test_parses_response_text_with_markdown_fencing(self) -> None:
        fenced_json = """```json
{
  "scenario_id": "scenario-001",
  "analysis": "Fenced analysis.",
  "cited_artifact_ids": ["logs.txt"],
  "proposed_actions": ["inspect logs"]
}
```"""
        response = parse_response_text(fenced_json)

        self.assertEqual(response.scenario_id, "scenario-001")
        self.assertEqual(response.analysis, "Fenced analysis.")
        self.assertEqual(response.cited_artifact_ids, ("logs.txt",))

    def test_rejects_invalid_response_text(self) -> None:
        with self.assertRaisesRegex(ValueError, "response text must be a non-empty string"):
            parse_response_text("   ")
        with self.assertRaisesRegex(ValueError, "response text is not valid JSON"):
            parse_response_text("not json")
            with self.assertRaisesRegex(ValueError, "proposed_actions must be a JSON array"):
                load_response(invalid_array_path)

            oversized_path = self.write_response(directory, '{"analysis":"' + "a" * 100 + '"}')
            with self.assertRaisesRegex(ValueError, "response exceeds maximum size"):
                load_response(oversized_path, max_bytes=16)


if __name__ == "__main__":
    unittest.main()