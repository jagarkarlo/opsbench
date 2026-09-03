import tempfile
import unittest
from pathlib import Path

from opsbench.adapters import FixtureResponseAdapter, GalleryFixtureResponseAdapter
from opsbench.performance_runner import (
    ProfiledRunExecution,
    ProfiledSuiteExecution,
    execute_run_profiled,
    execute_suite_profiled,
)
from opsbench.responses import BenchmarkResponse
from opsbench.scenarios import EvidenceArtifact, ScenarioManifest, ScenarioPack
from opsbench.scoring import EvaluatorProfile, KeywordRule


class ProfiledRunExecutionTests(unittest.TestCase):
    def _build_pack(self) -> ScenarioPack:
        return ScenarioPack(
            ScenarioManifest("scenario-001", "Test scenario", "kubernetes"),
            (EvidenceArtifact("logs.txt", "text/plain", b"test content"),),
        )

    def test_records_run_result_and_metrics(self) -> None:
        pack = self._build_pack()
        profile = EvaluatorProfile(
            scenario_id="scenario-001",
            diagnosis_rules=(KeywordRule("rule-1", "test", 1),),
            permitted_actions=("inspect logs",),
        )
        adapter = FixtureResponseAdapter(BenchmarkResponse("scenario-001", "Test response"))

        profiled = execute_run_profiled(
            run_id="test-run-1",
            pack=pack,
            profile=profile,
            adapter=adapter,
        )

        self.assertIsInstance(profiled, ProfiledRunExecution)
        self.assertEqual(profiled.run_result.run.run_id, "test-run-1")
        self.assertGreater(profiled.metrics.wall_time_seconds, 0)
        self.assertEqual(profiled.metrics.items_processed, 1)


class ProfiledSuiteExecutionTests(unittest.TestCase):
    def test_profiles_suite_and_computes_aggregate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            gallery_dir = Path(tmpdir) / "gallery"
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            # Create 3 test scenarios
            for i in range(3):
                scenario_dir = gallery_dir / f"scenario-{i+1:03d}"
                scenario_dir.mkdir(parents=True)

                scenario_id = f"scenario-{i+1:03d}"
                scenario_json = {"manifest":{"schema_version":"1.0","scenario_id":scenario_id,"title":"Test","category":"kubernetes"},"evidence":[{"artifact_id":"logs.txt","media_type":"text/plain","relative_path":"logs.txt"}]}
                (scenario_dir / "scenario.json").write_text(__import__("json").dumps(scenario_json), encoding="utf-8")
                (scenario_dir / "logs.txt").write_text("test logs\n", encoding="utf-8")
                evaluator_json = {"scenario_id":scenario_id,"diagnosis_rules":[{"rule_id":"test","keyword":"test","weight":1}],"permitted_actions":[]}
                (scenario_dir / "evaluator.json").write_text(__import__("json").dumps(evaluator_json), encoding="utf-8")

            adapter = GalleryFixtureResponseAdapter(
                {
                    "scenario-001": BenchmarkResponse("scenario-001", "Response 1"),
                    "scenario-002": BenchmarkResponse("scenario-002", "Response 2"),
                    "scenario-003": BenchmarkResponse("scenario-003", "Response 3"),
                }
            )

            profiled = execute_suite_profiled(
                gallery_directory=gallery_dir,
                output_directory=output_dir,
                adapter=adapter,
                run_prefix="test-suite",
            )

            self.assertIsInstance(profiled, ProfiledSuiteExecution)
            self.assertEqual(len(profiled.bundles), 3)
            self.assertEqual(len(profiled.individual_metrics), 3)

            for metrics in profiled.individual_metrics:
                self.assertGreater(metrics.wall_time_seconds, 0)
                self.assertEqual(metrics.items_processed, 1)

    def test_computes_aggregate_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            gallery_dir = Path(tmpdir) / "gallery"
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            # Create 2 test scenarios
            for i in range(2):
                scenario_dir = gallery_dir / f"scenario-{i+1:03d}"
                scenario_dir.mkdir(parents=True)

                scenario_id = f"scenario-{i+1:03d}"
                scenario_json = {"manifest":{"schema_version":"1.0","scenario_id":scenario_id,"title":"Test","category":"kubernetes"},"evidence":[{"artifact_id":"logs.txt","media_type":"text/plain","relative_path":"logs.txt"}]}
                (scenario_dir / "scenario.json").write_text(__import__("json").dumps(scenario_json), encoding="utf-8")
                (scenario_dir / "logs.txt").write_text("test logs\n", encoding="utf-8")
                evaluator_json = {"scenario_id":scenario_id,"diagnosis_rules":[{"rule_id":"test","keyword":"test","weight":1}],"permitted_actions":[]}
                (scenario_dir / "evaluator.json").write_text(__import__("json").dumps(evaluator_json), encoding="utf-8")

            adapter = GalleryFixtureResponseAdapter(
                {
                    "scenario-001": BenchmarkResponse("scenario-001", "Response 1"),
                    "scenario-002": BenchmarkResponse("scenario-002", "Response 2"),
                }
            )

            profiled = execute_suite_profiled(
                gallery_directory=gallery_dir,
                output_directory=output_dir,
                adapter=adapter,
            )

            aggregate = profiled.aggregate_metrics()
            total_individual = sum(m.wall_time_seconds for m in profiled.individual_metrics)

            self.assertAlmostEqual(aggregate.wall_time_seconds, total_individual, places=2)
            self.assertEqual(aggregate.items_processed, len(profiled.individual_metrics))


if __name__ == "__main__":
    unittest.main()
