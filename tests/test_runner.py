from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from opsbench.adapters import FixtureResponseAdapter, GalleryFixtureResponseAdapter
from opsbench.responses import BenchmarkResponse
from opsbench.runner import execute_run, execute_suite
from opsbench.scenarios import EvidenceArtifact, ScenarioManifest, ScenarioPack
from opsbench.scoring import EvaluatorProfile, KeywordRule
from opsbench.tracing import TraceTracer


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

    def test_executes_suite_across_gallery_directory(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            gallery = Path(temporary_directory) / "scenarios"
            output_dir = Path(temporary_directory) / "results"
            scenario = gallery / "alpha"
            scenario.mkdir(parents=True)
            (scenario / "scenario.json").write_text(
                '''{"manifest":{"schema_version":"1.0","scenario_id":"scenario-001","title":"Fictional scenario","category":"kubernetes"},"evidence":[{"artifact_id":"logs.txt","media_type":"text/plain","relative_path":"logs.txt"}]}''',
                encoding="utf-8",
            )
            (scenario / "logs.txt").write_text("synthetic logs\n", encoding="utf-8")
            (scenario / "evaluator.json").write_text(
                '''{"scenario_id":"scenario-001","diagnosis_rules":[{"rule_id":"synthetic","keyword":"synthetic","weight":2}],"permitted_actions":["inspect logs"]}''',
                encoding="utf-8",
            )
            adapter = GalleryFixtureResponseAdapter(
                {"scenario-001": BenchmarkResponse("scenario-001", "Synthetic analysis.")}
            )

            bundles = execute_suite(
                gallery_directory=gallery,
                output_directory=output_dir,
                adapter=adapter,
                run_prefix="test-suite",
                started_at=datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc),
            )

            self.assertEqual(len(bundles), 1)
            self.assertEqual(bundles[0].run.run_id, "test-suite-scenario-001")
            self.assertTrue((output_dir / "test-suite-scenario-001.json").is_file())

    def test_executes_suite_concurrently_with_max_workers(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            gallery = Path(temporary_directory) / "scenarios"
            output_dir = Path(temporary_directory) / "results"
            for name, sid in (("alpha", "scenario-001"), ("beta", "scenario-002")):
                scenario = gallery / name
                scenario.mkdir(parents=True)
                (scenario / "scenario.json").write_text(
                    f'''{{"manifest":{{"schema_version":"1.0","scenario_id":"{sid}","title":"Fictional scenario","category":"kubernetes"}},"evidence":[{{"artifact_id":"logs.txt","media_type":"text/plain","relative_path":"logs.txt"}}]}}''',
                    encoding="utf-8",
                )
                (scenario / "logs.txt").write_text("synthetic logs\n", encoding="utf-8")
                (scenario / "evaluator.json").write_text(
                    f'''{{"scenario_id":"{sid}","diagnosis_rules":[{{"rule_id":"synthetic","keyword":"synthetic","weight":2}}],"permitted_actions":["inspect logs"]}}''',
                    encoding="utf-8",
                )
            adapter = GalleryFixtureResponseAdapter(
                {
                    "scenario-001": BenchmarkResponse("scenario-001", "Alpha analysis."),
                    "scenario-002": BenchmarkResponse("scenario-002", "Beta analysis."),
                }
            )

            bundles = execute_suite(
                gallery_directory=gallery,
                output_directory=output_dir,
                adapter=adapter,
                run_prefix="parallel-suite",
                max_workers=2,
                started_at=datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc),
            )

            self.assertEqual(len(bundles), 2)
            self.assertEqual(bundles[0].run.run_id, "parallel-suite-scenario-001")
            self.assertEqual(bundles[1].run.run_id, "parallel-suite-scenario-002")

    def test_execute_run_records_a_trace_span_when_tracer_is_provided(self) -> None:
        tracer = TraceTracer("opsbench-test")
        adapter = FixtureResponseAdapter(BenchmarkResponse("scenario-001", "Synthetic analysis."))

        execute_run(
            run_id="fixture-run-001",
            pack=self.build_pack(),
            profile=self.build_profile(),
            adapter=adapter,
            tracer=tracer,
        )

        spans = tracer.recorded_spans()
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].name, "execute_run")
        self.assertEqual(dict(spans[0].attributes)["run_id"], "fixture-run-001")
        self.assertIsNotNone(spans[0].ended_at)

    def test_execute_suite_links_child_spans_to_a_shared_parent(self) -> None:
        tracer = TraceTracer()
        with TemporaryDirectory() as temporary_directory:
            gallery = Path(temporary_directory) / "scenarios"
            output_dir = Path(temporary_directory) / "results"
            scenario = gallery / "alpha"
            scenario.mkdir(parents=True)
            (scenario / "scenario.json").write_text(
                '''{"manifest":{"schema_version":"1.0","scenario_id":"scenario-001","title":"Fictional scenario","category":"kubernetes"},"evidence":[{"artifact_id":"logs.txt","media_type":"text/plain","relative_path":"logs.txt"}]}''',
                encoding="utf-8",
            )
            (scenario / "logs.txt").write_text("synthetic logs\n", encoding="utf-8")
            (scenario / "evaluator.json").write_text(
                '''{"scenario_id":"scenario-001","diagnosis_rules":[{"rule_id":"synthetic","keyword":"synthetic","weight":2}],"permitted_actions":["inspect logs"]}''',
                encoding="utf-8",
            )
            adapter = GalleryFixtureResponseAdapter(
                {"scenario-001": BenchmarkResponse("scenario-001", "Synthetic analysis.")}
            )

            execute_suite(
                gallery_directory=gallery,
                output_directory=output_dir,
                adapter=adapter,
                run_prefix="traced-suite",
                started_at=datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc),
                tracer=tracer,
            )

        spans = tracer.recorded_spans()
        self.assertEqual(len(spans), 2)
        suite_span, run_span = spans
        self.assertEqual(suite_span.name, "execute_suite")
        self.assertEqual(run_span.name, "execute_run")
        self.assertEqual(run_span.trace_id, suite_span.trace_id)
        self.assertEqual(run_span.parent_span_id, suite_span.span_id)
        self.assertIsNotNone(suite_span.ended_at)
        self.assertIsNotNone(run_span.ended_at)


if __name__ == "__main__":
    unittest.main()