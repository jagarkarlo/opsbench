import unittest

from opsbench.responses import BenchmarkResponse, SUPPORTED_RESPONSE_VERSION


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


if __name__ == "__main__":
    unittest.main()