import unittest

from opsbench.adapters import FixtureResponseAdapter, ResponseAdapter
from opsbench.responses import BenchmarkResponse
from opsbench.scenarios import EvidenceArtifact, ScenarioManifest, ScenarioPack


class FixtureAdapter:
    @property
    def adapter_name(self) -> str:
        return "fixture"

    def respond(self, pack: ScenarioPack) -> BenchmarkResponse:
        return BenchmarkResponse(
            scenario_id=pack.manifest.scenario_id,
            analysis="Synthetic response.",
            adapter_name=self.adapter_name,
        )


class ResponseAdapterTests(unittest.TestCase):
    def test_fixture_implementation_satisfies_response_adapter_contract(self) -> None:
        adapter: ResponseAdapter = FixtureAdapter()
        pack = ScenarioPack(
            ScenarioManifest("scenario-001", "Fictional scenario", "kubernetes"),
            (EvidenceArtifact("logs.txt", "text/plain", b"synthetic logs"),),
        )

        response = adapter.respond(pack)

        self.assertEqual(adapter.adapter_name, "fixture")
        self.assertEqual(response.scenario_id, "scenario-001")
        self.assertEqual(response.adapter_name, "fixture")

    def test_fixture_adapter_returns_a_normalized_response_for_matching_scenario(self) -> None:
        pack = ScenarioPack(
            ScenarioManifest("scenario-001", "Fictional scenario", "kubernetes"),
            (EvidenceArtifact("logs.txt", "text/plain", b"synthetic logs"),),
        )
        adapter = FixtureResponseAdapter(
            BenchmarkResponse("scenario-001", "Synthetic analysis.", model_name="fixture-model"),
            name="reference-fixture",
        )

        response = adapter.respond(pack)

        self.assertEqual(response.adapter_name, "reference-fixture")
        self.assertEqual(response.model_name, "fixture-model")

    def test_fixture_adapter_rejects_mismatched_scenario(self) -> None:
        pack = ScenarioPack(
            ScenarioManifest("scenario-001", "Fictional scenario", "kubernetes"),
            (EvidenceArtifact("logs.txt", "text/plain", b"synthetic logs"),),
        )
        adapter = FixtureResponseAdapter(BenchmarkResponse("other-scenario", "Synthetic analysis."))

        with self.assertRaisesRegex(ValueError, "fixture response scenario_id must match"):
            adapter.respond(pack)


if __name__ == "__main__":
    unittest.main()