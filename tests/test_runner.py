from datetime import datetime, timezone
import unittest

from opsbench.adapters import FixtureResponseAdapter
from opsbench.responses import BenchmarkResponse
from opsbench.runner import execute_run
from opsbench.scenarios import EvidenceArtifact, ScenarioManifest, ScenarioPack
from opsbench.scoring import EvaluatorProfile, KeywordRule


class BenchmarkRunnerTests(unittest.TestCase):
    def build_pack(self) -> ScenarioPack:
        return ScenarioPack(
            ScenarioManifest("scenario-001", "Fictional scenario", "kubernetes"),
            (EvidenceArtifact("logs.txt", "text/plain", b"synthetic logs"),),
        )

    def build_profile(self) -> EvaluatorProfile:
        return EvaluatorProfile(
            scenario_id="scenario-001",
            diagnosis_rules=(KeywordRule("synthetic", "synthetic", weight=2),),
            permitted_actions=("inspect logs",),
        )

    def test_executes_fixture_adapter_into_immutable_run_and_report(self) -> None:
        pack = self.build_pack()
        profile = self.build_profile()
        adapter = FixtureResponseAdapter(
            BenchmarkResponse(
                scenario_id="scenario-001",
                analysis="Synthetic analysis based on synthetic logs.",
                cited_artifact_ids=("logs.txt",),
                proposed_actions=("inspect logs",),
                model_name="fixture-model",
            ),
            name="fixture",
        )

        result = execute_run(
            run_id="fixture-run-001",
            pack=pack,
            profile=profile,
            adapter=adapter,
            started_at=datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(result.run.runner_kind, "fixture")
        self.assertEqual(result.run.scenario_pack_hash, pack.content_hash())
        self.assertEqual(result.run.evaluator_profile_hash, profile.content_hash())
        self.assertEqual(result.report.total, 8)

    def test_rejects_profile_for_a_different_scenario(self) -> None:
        adapter = FixtureResponseAdapter(BenchmarkResponse("scenario-001", "Synthetic analysis."))
        profile = EvaluatorProfile(
            scenario_id="other-scenario",
            diagnosis_rules=(KeywordRule("synthetic", "synthetic"),),
        )

        with self.assertRaisesRegex(ValueError, "profile scenario_id must match"):
            execute_run(run_id="fixture-run-001", pack=self.build_pack(), profile=profile, adapter=adapter)


if __name__ == "__main__":
    unittest.main()