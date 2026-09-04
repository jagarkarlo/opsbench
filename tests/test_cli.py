from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from opsbench.cli import build_parser, main, parse_metadata
from opsbench.runs import BenchmarkRun, ResultBundle, write_result_bundle
from opsbench.scoring import Score, ScoreReport


class CliParserTests(unittest.TestCase):
    def test_prints_version_and_exits(self) -> None:
        import opsbench

        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            build_parser().parse_args(["--version"])

        self.assertEqual(raised.exception.code, 0)
        self.assertIn(opsbench.__version__, output.getvalue())

    def test_parses_scenario_validate_command(self) -> None:
        parsed = build_parser().parse_args(["scenario", "validate", "scenarios/example"])

        self.assertEqual(parsed.command, "scenario")
        self.assertEqual(parsed.scenario_command, "validate")
        self.assertEqual(parsed.path, "scenarios/example")

    def test_parses_scenario_list_command(self) -> None:
        parsed = build_parser().parse_args(["scenario", "list", "scenarios"])

        self.assertEqual(parsed.scenario_command, "list")
        self.assertEqual(parsed.path, "scenarios")

    def test_parses_scenario_audit_command(self) -> None:
        parsed = build_parser().parse_args(["scenario", "audit", "scenarios"])

        self.assertEqual(parsed.command, "scenario")
        self.assertEqual(parsed.scenario_command, "audit")
        self.assertEqual(parsed.path, "scenarios")

    def test_parses_scenario_prompt_command(self) -> None:
        parsed = build_parser().parse_args(
            ["scenario", "prompt", "scenarios/example", "--instruction", "Custom rule"]
        )

        self.assertEqual(parsed.command, "scenario")
        self.assertEqual(parsed.scenario_command, "prompt")
        self.assertEqual(parsed.path, "scenarios/example")
        self.assertEqual(parsed.instruction, "Custom rule")

    def test_parses_scenario_lint_command(self) -> None:
        parsed = build_parser().parse_args(["scenario", "lint", "scenarios/example"])

        self.assertEqual(parsed.command, "scenario")
        self.assertEqual(parsed.scenario_command, "lint")
        self.assertEqual(parsed.path, "scenarios/example")

    def test_parses_response_evaluate_command(self) -> None:
        parsed = build_parser().parse_args(
            ["response", "evaluate", "scenarios/example", "responses/example.json"]
        )

        self.assertEqual(parsed.command, "response")
        self.assertEqual(parsed.response_command, "evaluate")
        self.assertEqual(parsed.scenario_path, "scenarios/example")
        self.assertEqual(parsed.response_path, "responses/example.json")

    def test_parses_fixture_run_command(self) -> None:
        parsed = build_parser().parse_args(
            [
                "run",
                "fixture",
                "scenarios/example",
                "responses/example.json",
                "results/run.json",
                "--run-id",
                "fixture-run-001",
            ]
        )

        self.assertEqual(parsed.command, "run")
        self.assertEqual(parsed.run_command, "fixture")
        self.assertEqual(parsed.run_id, "fixture-run-001")
        self.assertEqual(parsed.output_path, "results/run.json")

    def test_parses_performance_output_option(self) -> None:
        parsed = build_parser().parse_args(
            [
                "run",
                "fixture",
                "scenarios/example",
                "responses/example.json",
                "results/run.json",
                "--run-id",
                "fixture-run-001",
                "--performance-output",
                "results/performance.json",
            ]
        )

        self.assertEqual(parsed.performance_output, "results/performance.json")

    def test_parses_failure_injection_options_for_single_runs(self) -> None:
        parsed = build_parser().parse_args(
            [
                "run",
                "fixture",
                "scenarios/example",
                "responses/example.json",
                "results/run.json",
                "--run-id",
                "fixture-run-001",
                "--inject-failure",
                "timeout",
                "--inject-failure-scenario",
                "scenario-001",
            ]
        )

        self.assertEqual(parsed.inject_failure, "timeout")
        self.assertEqual(parsed.inject_failure_scenario, ["scenario-001"])

    def test_parses_human_run_command(self) -> None:
        parsed = build_parser().parse_args(
            [
                "run",
                "human",
                "scenarios/example",
                "responses/example.json",
                "results/run.json",
                "--run-id",
                "human-run-001",
            ]
        )

        self.assertEqual(parsed.command, "run")
        self.assertEqual(parsed.run_command, "human")
        self.assertEqual(parsed.run_id, "human-run-001")

    def test_parses_suite_run_command(self) -> None:
        parsed = build_parser().parse_args(
            [
                "run",
                "suite",
                "scenarios",
                "results",
                "--run-prefix",
                "benchmark-run",
                "--max-workers",
                "4",
            ]
        )

        self.assertEqual(parsed.command, "run")
        self.assertEqual(parsed.run_command, "suite")
        self.assertEqual(parsed.gallery_path, "scenarios")
        self.assertEqual(parsed.output_dir, "results")
        self.assertEqual(parsed.run_prefix, "benchmark-run")
        self.assertEqual(parsed.max_workers, 4)

    def test_parses_suite_failure_injection_options(self) -> None:
        parsed = build_parser().parse_args(
            [
                "run",
                "suite",
                "scenarios",
                "results",
                "--inject-failure",
                "timeout",
                "--inject-failure-scenario",
                "scenario-002",
            ]
        )

        self.assertEqual(parsed.inject_failure, "timeout")
        self.assertEqual(parsed.inject_failure_scenario, ["scenario-002"])

    def test_parses_openai_run_command(self) -> None:
        parsed = build_parser().parse_args(
            [
                "run",
                "openai",
                "scenarios/example",
                "results/run.json",
                "--model",
                "gpt-4o",
                "--api-base",
                "http://localhost:11434/v1",
                "--run-id",
                "openai-run-001",
                "--otlp-endpoint",
                "http://collector:4318/v1/traces",
            ]
        )

        self.assertEqual(parsed.command, "run")
        self.assertEqual(parsed.run_command, "openai")
        self.assertEqual(parsed.model, "gpt-4o")
        self.assertEqual(parsed.api_base, "http://localhost:11434/v1")
        self.assertEqual(parsed.run_id, "openai-run-001")
        self.assertEqual(parsed.otlp_endpoint, "http://collector:4318/v1/traces")

    def test_parses_serve_command(self) -> None:
        parsed = build_parser().parse_args(
            ["serve", "--host", "0.0.0.0", "--port", "9090", "--db", "test.db"]
        )

        self.assertEqual(parsed.command, "serve")
        self.assertEqual(parsed.host, "0.0.0.0")
        self.assertEqual(parsed.port, 9090)
        self.assertEqual(parsed.db, "test.db")

    def test_parses_canonical_run_metadata(self) -> None:
        parsed = build_parser().parse_args(
            [
                "run",
                "fixture",
                "scenarios/example",
                "responses/example.json",
                "results/run.json",
                "--run-id",
                "fixture-run-001",
                "--metadata",
                "temperature=0",
                "--metadata",
                "seed=42",
            ]
        )

        self.assertEqual(
            parse_metadata(parsed.metadata), (("seed", "42"), ("temperature", "0"))
        )

    def test_rejects_malformed_or_duplicate_run_metadata(self) -> None:
        with self.assertRaisesRegex(ValueError, "key=value"):
            parse_metadata(["seed"])
        with self.assertRaisesRegex(ValueError, "keys must be unique"):
            parse_metadata(["seed=42", "seed=43"])

    def test_parses_result_comparison_command(self) -> None:
        parsed = build_parser().parse_args(
            ["compare", "results", "results/first.json", "results/second.json", "--format", "markdown"]
        )

        self.assertEqual(parsed.command, "compare")
        self.assertEqual(parsed.compare_command, "results")
        self.assertEqual(parsed.bundle_paths, ["results/first.json", "results/second.json"])
        self.assertEqual(parsed.format, "markdown")

    def test_executes_fixture_run_and_writes_result_bundle(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            scenario = directory / "scenario"
            scenario.mkdir()
            (scenario / "scenario.json").write_text(
                """{
                    "manifest": {
                        "schema_version": "1.0",
                        "scenario_id": "scenario-001",
                        "title": "Fictional scenario",
                        "category": "kubernetes"
                    },
                    "evidence": [{
                        "artifact_id": "logs.txt",
                        "media_type": "text/plain",
                        "relative_path": "logs.txt"
                    }]
                }""",
                encoding="utf-8",
            )
            (scenario / "logs.txt").write_text("synthetic logs\n", encoding="utf-8")
            (scenario / "evaluator.json").write_text(
                """{
                    "scenario_id": "scenario-001",
                    "diagnosis_rules": [{"rule_id":"synthetic","keyword":"synthetic","weight":2}],
                    "permitted_actions": ["inspect logs"]
                }""",
                encoding="utf-8",
            )
            response_path = directory / "response.json"
            response_path.write_text(
                """{
                    "scenario_id": "scenario-001",
                    "analysis": "Synthetic analysis.",
                    "cited_artifact_ids": ["logs.txt"],
                    "proposed_actions": ["inspect logs"],
                    "model_name": "fixture-model"
                }""",
                encoding="utf-8",
            )
            output_path = directory / "results" / "fixture-run.json"
            performance_path = directory / "results" / "performance.json"
            output = io.StringIO()

            with patch("opsbench.cli.TraceTracer") as tracer_class:
                with redirect_stdout(output):
                    exit_code = main(
                        [
                            "run",
                            "fixture",
                            str(scenario),
                            str(response_path),
                            str(output_path),
                            "--run-id",
                            "fixture-run-001",
                            "--otlp-endpoint",
                            "http://collector:4318/v1/traces",
                            "--performance-output",
                            str(performance_path),
                        ]
                    )

            tracer_class.return_value.export_otlp.assert_called_once_with(
                "http://collector:4318/v1/traces"
            )

            command_result = json.loads(output.getvalue())
            bundle = json.loads(output_path.read_text(encoding="utf-8"))
            performance = json.loads(performance_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(command_result["run"]["run_id"], "fixture-run-001")
        self.assertEqual(command_result["report"]["total"], 8)
        self.assertEqual(bundle["run"]["model_name"], "fixture-model")
        self.assertEqual(bundle["run"]["metadata"], {})
        self.assertEqual(len(command_result["bundle_hash"]), 64)
        self.assertEqual(performance["metrics"]["items_processed"], 1)
        self.assertGreater(performance["metrics"]["wall_time_seconds"], 0)

    def test_executes_human_run_and_writes_result_bundle(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            scenario = directory / "scenario"
            scenario.mkdir()
            (scenario / "scenario.json").write_text(
                '''{"manifest":{"schema_version":"1.0","scenario_id":"scenario-001","title":"Fictional scenario","category":"kubernetes"},"evidence":[{"artifact_id":"logs.txt","media_type":"text/plain","relative_path":"logs.txt"}]}''',
                encoding="utf-8",
            )
            (scenario / "logs.txt").write_text("synthetic logs\n", encoding="utf-8")
            (scenario / "evaluator.json").write_text(
                '''{"scenario_id":"scenario-001","diagnosis_rules":[{"rule_id":"synthetic","keyword":"synthetic","weight":2}],"permitted_actions":["inspect logs"]}''',
                encoding="utf-8",
            )
            response_path = directory / "response.json"
            response_path.write_text(
                '''{"scenario_id":"scenario-001","analysis":"Synthetic human analysis.","cited_artifact_ids":["logs.txt"],"proposed_actions":["inspect logs"],"model_name":"Karlo"}''',
                encoding="utf-8",
            )
            output_path = directory / "results" / "human-run.json"
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    [
                        "run",
                        "human",
                        str(scenario),
                        str(response_path),
                        str(output_path),
                        "--run-id",
                        "human-run-001",
                    ]
                )

            command_result = json.loads(output.getvalue())
            bundle = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(command_result["run"]["runner_kind"], "human")
        self.assertEqual(bundle["run"]["model_name"], "Karlo")

    def test_reports_injected_failure_without_writing_a_result_bundle(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            scenario = directory / "scenario"
            scenario.mkdir()
            (scenario / "scenario.json").write_text(
                '''{"manifest":{"schema_version":"1.0","scenario_id":"scenario-001","title":"Fictional scenario","category":"kubernetes"},"evidence":[{"artifact_id":"logs.txt","media_type":"text/plain","relative_path":"logs.txt"}]}''',
                encoding="utf-8",
            )
            (scenario / "logs.txt").write_text("synthetic logs\n", encoding="utf-8")
            (scenario / "evaluator.json").write_text(
                '''{"scenario_id":"scenario-001","diagnosis_rules":[{"rule_id":"synthetic","keyword":"synthetic","weight":2}]}''',
                encoding="utf-8",
            )
            response_path = directory / "response.json"
            response_path.write_text(
                '''{"scenario_id":"scenario-001","analysis":"Synthetic analysis."}''',
                encoding="utf-8",
            )
            output_path = directory / "results" / "failure.json"
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    [
                        "run",
                        "fixture",
                        str(scenario),
                        str(response_path),
                        str(output_path),
                        "--run-id",
                        "failure-run-001",
                        "--inject-failure",
                        "timeout",
                    ]
                )

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 3)
        self.assertEqual(result["status"], "injected_failure")
        self.assertEqual(result["failure"], {"mode": "timeout", "scenario_id": "scenario-001"})
        self.assertFalse(output_path.exists())

    def test_writes_and_compares_performance_baselines(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            scenario = directory / "scenario"
            scenario.mkdir()
            (scenario / "scenario.json").write_text(
                '''{"manifest":{"schema_version":"1.0","scenario_id":"scenario-001","title":"Fictional scenario","category":"kubernetes"},"evidence":[{"artifact_id":"logs.txt","media_type":"text/plain","relative_path":"logs.txt"}]}''',
                encoding="utf-8",
            )
            (scenario / "logs.txt").write_text("synthetic logs\n", encoding="utf-8")
            (scenario / "evaluator.json").write_text(
                '''{"scenario_id":"scenario-001","diagnosis_rules":[{"rule_id":"synthetic","keyword":"synthetic","weight":2}],"permitted_actions":["inspect logs"]}''',
                encoding="utf-8",
            )
            response_path = directory / "response.json"
            response_path.write_text(
                '''{"scenario_id":"scenario-001","analysis":"Synthetic analysis.","cited_artifact_ids":["logs.txt"],"proposed_actions":["inspect logs"],"model_name":"fixture-model"}''',
                encoding="utf-8",
            )
            baseline_path = directory / "baseline.json"
            first_exit_code = main(
                [
                    "run",
                    "fixture",
                    str(scenario),
                    str(response_path),
                    str(directory / "first.json"),
                    "--run-id",
                    "first-run",
                    "--write-performance-baseline",
                    str(baseline_path),
                ]
            )
            self.assertEqual(first_exit_code, 0)
            self.assertTrue(baseline_path.is_file())

            regression_baseline_path = directory / "regression-baseline.json"
            regression_baseline_path.write_text(
                '''{"created_at_utc":"2026-09-03T12:00:00+00:00","items_processed":1,"name":"run-scenario-001","wall_time_seconds":0.000000000001}''',
                encoding="utf-8",
            )
            output = io.StringIO()
            with redirect_stdout(output):
                second_exit_code = main(
                    [
                        "run",
                        "fixture",
                        str(scenario),
                        str(response_path),
                        str(directory / "second.json"),
                        "--run-id",
                        "second-run",
                        "--compare-performance-baseline",
                        str(regression_baseline_path),
                    ]
                )

        self.assertEqual(second_exit_code, 2)
        self.assertIn('"run_id": "second-run"', output.getvalue())

    def test_runs_backup_recovery_drill_via_store_cli(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            database_path = directory / "results.db"
            bundle_path = directory / "bundle.json"
            run = BenchmarkRun(
                run_id="drill-run-001",
                runner_kind="fixture",
                started_at="2026-09-03T12:00:00Z",
                scenario_pack_hash="a" * 64,
                evaluator_profile_hash="b" * 64,
                response_hash="c" * 64,
            )
            report = ScoreReport(
                scenario_id="scenario-001",
                response_hash="c" * 64,
                diagnosis=Score.GOOD,
                evidence=Score.FULL,
                actions=Score.LOW,
                safety=Score.FULL,
                explanation="synthetic recovery drill result",
            )
            write_result_bundle(bundle_path, ResultBundle(run, report))
            self.assertEqual(main(["store", "index", str(database_path), str(bundle_path)]), 0)

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "store",
                        "drill",
                        str(database_path),
                        str(directory / "backup.json"),
                        str(directory / "restored.db"),
                    ]
                )

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["source_count"], 1)
        self.assertEqual(result["restored_count"], 1)

    def test_runs_recovery_drill_series_via_store_cli(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            database_path = directory / "results.db"
            bundle_path = directory / "bundle.json"
            run = BenchmarkRun(
                run_id="series-run-001",
                runner_kind="fixture",
                started_at="2026-09-03T12:00:00Z",
                scenario_pack_hash="a" * 64,
                evaluator_profile_hash="b" * 64,
                response_hash="c" * 64,
            )
            report = ScoreReport(
                scenario_id="scenario-001",
                response_hash="c" * 64,
                diagnosis=Score.GOOD,
                evidence=Score.FULL,
                actions=Score.LOW,
                safety=Score.FULL,
                explanation="synthetic recovery series result",
            )
            write_result_bundle(bundle_path, ResultBundle(run, report))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["store", "index", str(database_path), str(bundle_path)]), 0)

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "store",
                        "drill-series",
                        str(database_path),
                        str(directory / "drills"),
                        "--attempts",
                        "2",
                        "--retention",
                        "1",
                    ]
                )

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["attempt_count"], 2)
        self.assertEqual(result["retained_attempts"], 1)
        self.assertEqual(result["removed_attempts"], 1)

    def test_runs_schedule_tick_via_store_cli(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            database_path = directory / "results.db"
            bundle_path = directory / "bundle.json"
            run = BenchmarkRun(
                run_id="schedule-run-001",
                runner_kind="fixture",
                started_at="2026-09-03T12:00:00Z",
                scenario_pack_hash="a" * 64,
                evaluator_profile_hash="b" * 64,
                response_hash="c" * 64,
            )
            report = ScoreReport(
                scenario_id="scenario-001",
                response_hash="c" * 64,
                diagnosis=Score.GOOD,
                evidence=Score.FULL,
                actions=Score.LOW,
                safety=Score.FULL,
                explanation="synthetic scheduled recovery result",
            )
            write_result_bundle(bundle_path, ResultBundle(run, report))
            with redirect_stdout(io.StringIO()):
                main(["store", "index", str(database_path), str(bundle_path)])

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "store",
                        "schedule-tick",
                        str(database_path),
                        str(directory / "drills"),
                        str(directory / "history.jsonl"),
                        "--run-id",
                        "tick-001",
                        "--alert-path",
                        str(directory / "alert.json"),
                    ]
                )

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["run_id"], "tick-001")
        self.assertFalse((directory / "alert.json").exists())

    def test_schedule_tick_cli_returns_three_on_recorded_failure(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "store",
                        "schedule-tick",
                        str(directory / "missing.db"),
                        str(directory / "drills"),
                        str(directory / "history.jsonl"),
                        "--run-id",
                        "tick-failed",
                        "--alert-path",
                        str(directory / "alert.json"),
                    ]
                )

            alert_exists = (directory / "alert.json").is_file()
        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 3)
        self.assertEqual(result["status"], "failed")
        self.assertTrue(alert_exists)

    def test_runs_bounded_chaos_matrix_via_cli(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            gallery = directory / "scenarios"
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
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "run",
                        "chaos-matrix",
                        str(gallery),
                        str(directory / "matrix"),
                        "--iterations",
                        "2",
                        "--mode",
                        "timeout",
                        "--mode",
                        "missing_evidence",
                    ]
                )

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 3)
        self.assertEqual(result["case_count"], 4)
        self.assertEqual(result["failure_count"], 2)
        self.assertEqual(result["status"], "completed_with_injected_failures")

    def test_executes_suite_run_and_writes_result_bundles(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            gallery = directory / "scenarios"
            scenario = gallery / "alpha"
            scenario.mkdir(parents=True)
            responses_dir = scenario / "responses"
            responses_dir.mkdir()
            (scenario / "scenario.json").write_text(
                '''{"manifest":{"schema_version":"1.0","scenario_id":"scenario-001","title":"Fictional scenario","category":"kubernetes"},"evidence":[{"artifact_id":"logs.txt","media_type":"text/plain","relative_path":"logs.txt"}]}''',
                encoding="utf-8",
            )
            (scenario / "logs.txt").write_text("synthetic logs\n", encoding="utf-8")
            (scenario / "evaluator.json").write_text(
                '''{"scenario_id":"scenario-001","diagnosis_rules":[{"rule_id":"synthetic","keyword":"synthetic","weight":2}],"permitted_actions":["inspect logs"]}''',
                encoding="utf-8",
            )
            (responses_dir / "reference-response.json").write_text(
                '''{"scenario_id":"scenario-001","analysis":"Synthetic analysis.","cited_artifact_ids":["logs.txt"],"proposed_actions":["inspect logs"],"model_name":"reference-fixture"}''',
                encoding="utf-8",
            )
            output_dir = directory / "results"
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    [
                        "run",
                        "suite",
                        str(gallery),
                        str(output_dir),
                        "--run-prefix",
                        "test-suite",
                    ]
                )

            command_result = json.loads(output.getvalue())

            self.assertEqual(exit_code, 0)
            self.assertEqual(command_result["bundle_count"], 1)
            self.assertEqual(command_result["scenario_ids"], ["scenario-001"])
            self.assertTrue((output_dir / "test-suite-scenario-001.json").is_file())

    def test_reports_partial_suite_outcome_for_injected_failure(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            gallery = directory / "scenarios"
            for name, scenario_id in (("alpha", "scenario-001"), ("beta", "scenario-002")):
                scenario = gallery / name
                responses = scenario / "responses"
                responses.mkdir(parents=True)
                (scenario / "scenario.json").write_text(
                    f'''{{"manifest":{{"schema_version":"1.0","scenario_id":"{scenario_id}","title":"Fictional scenario","category":"kubernetes"}},"evidence":[{{"artifact_id":"logs.txt","media_type":"text/plain","relative_path":"logs.txt"}}]}}''',
                    encoding="utf-8",
                )
                (scenario / "logs.txt").write_text("synthetic logs\n", encoding="utf-8")
                (scenario / "evaluator.json").write_text(
                    f'''{{"scenario_id":"{scenario_id}","diagnosis_rules":[{{"rule_id":"synthetic","keyword":"synthetic","weight":1}}]}}''',
                    encoding="utf-8",
                )
                (responses / "reference-response.json").write_text(
                    f'''{{"scenario_id":"{scenario_id}","analysis":"Synthetic analysis."}}''',
                    encoding="utf-8",
                )
            output_dir = directory / "results"
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    [
                        "run",
                        "suite",
                        str(gallery),
                        str(output_dir),
                        "--run-prefix",
                        "partial-suite",
                        "--inject-failure",
                        "timeout",
                        "--inject-failure-scenario",
                        "scenario-002",
                    ]
                )
            successful_bundle_exists = (output_dir / "partial-suite-scenario-001.json").is_file()
            failed_bundle_exists = (output_dir / "partial-suite-scenario-002.json").exists()

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 3)
        self.assertEqual(result["status"], "completed_with_injected_failures")
        self.assertEqual(result["scenario_ids"], ["scenario-001"])
        self.assertEqual(
            result["failures"],
            [{"failure": {"mode": "timeout", "scenario_id": "scenario-002"}, "run_id": "partial-suite-scenario-002"}],
        )
        self.assertTrue(successful_bundle_exists)
        self.assertFalse(failed_bundle_exists)

    def test_reports_partial_suite_performance_with_injected_failure(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            gallery = directory / "scenarios"
            for name, scenario_id in (("alpha", "scenario-001"), ("beta", "scenario-002")):
                scenario = gallery / name
                responses = scenario / "responses"
                responses.mkdir(parents=True)
                (scenario / "scenario.json").write_text(
                    f'''{{"manifest":{{"schema_version":"1.0","scenario_id":"{scenario_id}","title":"Fictional scenario","category":"kubernetes"}},"evidence":[{{"artifact_id":"logs.txt","media_type":"text/plain","relative_path":"logs.txt"}}]}}''',
                    encoding="utf-8",
                )
                (scenario / "logs.txt").write_text("synthetic logs\n", encoding="utf-8")
                (scenario / "evaluator.json").write_text(
                    f'''{{"scenario_id":"{scenario_id}","diagnosis_rules":[{{"rule_id":"synthetic","keyword":"synthetic","weight":1}}]}}''',
                    encoding="utf-8",
                )
                (responses / "reference-response.json").write_text(
                    f'''{{"scenario_id":"{scenario_id}","analysis":"Synthetic analysis."}}''',
                    encoding="utf-8",
                )
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "run",
                        "suite",
                        str(gallery),
                        str(directory / "results"),
                        "--inject-failure",
                        "timeout",
                        "--inject-failure-scenario",
                        "scenario-002",
                        "--performance-output",
                        str(directory / "performance.json"),
                    ]
                )

            result = json.loads(output.getvalue())
            performance = json.loads((directory / "performance.json").read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 3)
        self.assertEqual(result["status"], "completed_with_injected_failures")
        self.assertEqual(performance["completed_count"], 1)
        self.assertEqual(performance["failed_count"], 1)
        self.assertEqual(performance["scenario_count"], 2)
        self.assertEqual(len(performance["metrics"]), 1)

    def test_lints_scenario_via_cli(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            scenario = Path(temporary_directory) / "kubernetes-image-reference-001"
            scenario.mkdir()
            (scenario / "scenario.json").write_text(
                '''{"manifest":{"schema_version":"1.0","scenario_id":"kubernetes-image-reference-001","title":"Fictional scenario","category":"kubernetes"},"evidence":[{"artifact_id":"pod-logs.txt","media_type":"text/plain","relative_path":"pod-logs.txt"}]}''',
                encoding="utf-8",
            )
            (scenario / "pod-logs.txt").write_text("restarted\n", encoding="utf-8")
            (scenario / "evaluator.json").write_text(
                '''{"scenario_id":"kubernetes-image-reference-001","diagnosis_rules":[{"rule_id":"restarted","keyword":"restarted","weight":1}],"permitted_actions":[]}''',
                encoding="utf-8",
            )
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(["scenario", "lint", str(scenario)])

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["status"], "clean")
        self.assertEqual(result["issue_count"], 0)

    def test_indexes_and_queries_bundles_via_store_cli(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            run = BenchmarkRun(
                run_id="store-run-001",
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
                evidence=Score.ZERO,
                actions=Score.ZERO,
                safety=Score.ZERO,
                explanation="Synthetic result.",
            )
            bundle_path = directory / "result.json"
            write_result_bundle(bundle_path, ResultBundle(run, report))

            db_path = directory / "store.db"

            index_output = io.StringIO()
            with redirect_stdout(index_output):
                index_exit = main(["store", "index", str(db_path), str(bundle_path)])

            index_res = json.loads(index_output.getvalue())
            self.assertEqual(index_exit, 0)
            self.assertEqual(index_res["indexed_count"], 1)

            query_output = io.StringIO()
            with redirect_stdout(query_output):
                query_exit = main(["store", "query", str(db_path), "--scenario-id", "scenario-001"])

            query_res = json.loads(query_output.getvalue())
            self.assertEqual(query_exit, 0)
            self.assertEqual(query_res["count"], 1)
            self.assertEqual(query_res["results"][0]["run"]["run_id"], "store-run-001")

            export_file = directory / "archive.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit = main(["store", "export", str(db_path), str(export_file)])

            export_res = json.loads(export_output.getvalue())
            self.assertEqual(export_exit, 0)
            self.assertEqual(export_res["exported_count"], 1)

            db_import_path = directory / "imported_store.db"
            import_output = io.StringIO()
            with redirect_stdout(import_output):
                import_exit = main(["store", "import", str(db_import_path), str(export_file)])

            import_res = json.loads(import_output.getvalue())
            self.assertEqual(import_exit, 0)
            self.assertEqual(import_res["imported_count"], 1)

    def test_backs_up_and_restores_bundles_via_store_cli(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            run = BenchmarkRun(
                run_id="backup-run-001",
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
                evidence=Score.ZERO,
                actions=Score.ZERO,
                safety=Score.ZERO,
                explanation="Synthetic result.",
            )
            bundle_path = directory / "result.json"
            write_result_bundle(bundle_path, ResultBundle(run, report))
            source_db_path = directory / "source.db"

            with redirect_stdout(io.StringIO()):
                main(["store", "index", str(source_db_path), str(bundle_path)])

            archive_path = directory / "backup.json"
            backup_output = io.StringIO()
            with redirect_stdout(backup_output):
                backup_exit = main(["store", "backup", str(source_db_path), str(archive_path)])

            backup_result = json.loads(backup_output.getvalue())
            self.assertEqual(backup_exit, 0)
            self.assertEqual(backup_result["status"], "success")
            self.assertEqual(backup_result["bundle_count"], 1)

            restored_db_path = directory / "restored.db"
            restore_output = io.StringIO()
            with redirect_stdout(restore_output):
                restore_exit = main(["store", "restore", str(archive_path), str(restored_db_path)])

            restore_result = json.loads(restore_output.getvalue())
            self.assertEqual(restore_exit, 0)
            self.assertEqual(restore_result["status"], "success")
            self.assertEqual(restore_result["bundle_count"], 1)

            query_output = io.StringIO()
            with redirect_stdout(query_output):
                query_exit = main(["store", "query", str(restored_db_path)])

        query_result = json.loads(query_output.getvalue())
        self.assertEqual(query_exit, 0)
        self.assertEqual(query_result["count"], 1)
        self.assertEqual(query_result["results"][0]["run"]["run_id"], "backup-run-001")

    def test_compares_saved_result_bundles(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            paths = []
            for index, diagnosis_score in enumerate((Score.FULL, Score.GOOD), start=1):
                response_hash = ("a" if index == 1 else "b") * 64
                run = BenchmarkRun(
                    run_id=f"fixture-run-{index}",
                    runner_kind="fixture",
                    started_at="2026-08-26T12:00:00Z",
                    scenario_pack_hash="c" * 64,
                    evaluator_profile_hash="d" * 64,
                    response_hash=response_hash,
                    model_name="fixture-model",
                )
                report = ScoreReport(
                    scenario_id="scenario-001",
                    response_hash=response_hash,
                    diagnosis=diagnosis_score,
                    evidence=Score.ZERO,
                    actions=Score.ZERO,
                    safety=Score.ZERO,
                    explanation="Synthetic result.",
                )
                path = directory / f"result-{index}.json"
                write_result_bundle(path, ResultBundle(run, report))
                paths.append(str(path))
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(["compare", "results", *paths])

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["scenario_id"], "scenario-001")
        self.assertEqual(result["trials"][0]["trial_count"], 2)
        self.assertEqual(result["trials"][0]["average_score"], 3.5)

    def test_compares_saved_result_bundles_in_markdown_format(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            paths = []
            for index, diagnosis_score in enumerate((Score.FULL, Score.GOOD), start=1):
                response_hash = ("a" if index == 1 else "b") * 64
                run = BenchmarkRun(
                    run_id=f"fixture-run-{index}",
                    runner_kind="fixture",
                    started_at="2026-08-26T12:00:00Z",
                    scenario_pack_hash="c" * 64,
                    evaluator_profile_hash="d" * 64,
                    response_hash=response_hash,
                    model_name="fixture-model",
                )
                report = ScoreReport(
                    scenario_id="scenario-001",
                    response_hash=response_hash,
                    diagnosis=diagnosis_score,
                    evidence=Score.ZERO,
                    actions=Score.ZERO,
                    safety=Score.ZERO,
                    explanation="Synthetic result.",
                )
                path = directory / f"result-{index}.json"
                write_result_bundle(path, ResultBundle(run, report))
                paths.append(str(path))
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(["compare", "results", *paths, "--format", "markdown"])

        markdown_report = output.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("# OpsBench Comparison Report", markdown_report)
        self.assertIn("**Scenario**: `scenario-001`", markdown_report)
        self.assertIn("| fixture-model | 2 | 7 | 3.50 |", markdown_report)

    def test_validates_scenario_directory_and_prints_pack_identity(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            (directory / "scenario.json").write_text(
                """{
                    "manifest": {
                        "schema_version": "1.0",
                        "scenario_id": "kubernetes-crashloop-001",
                        "title": "Diagnose a fictional CrashLoopBackOff deployment",
                        "category": "kubernetes"
                    },
                    "evidence": [{
                        "artifact_id": "pod-logs.txt",
                        "media_type": "text/plain",
                        "relative_path": "pod-logs.txt"
                    }]
                }""",
                encoding="utf-8",
            )
            (directory / "pod-logs.txt").write_text(
                "fictional workload restarted after a configuration error\n",
                encoding="utf-8",
            )
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(["scenario", "validate", str(directory)])

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["scenario_id"], "kubernetes-crashloop-001")
        self.assertEqual(result["evidence_count"], 1)
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["pack_hash"]), 64)

    def test_renders_scenario_prompt_via_cli(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            (directory / "scenario.json").write_text(
                """{
                    "manifest": {
                        "schema_version": "1.0",
                        "scenario_id": "kubernetes-crashloop-001",
                        "title": "Diagnose a fictional CrashLoopBackOff deployment",
                        "category": "kubernetes"
                    },
                    "evidence": [{
                        "artifact_id": "pod-logs.txt",
                        "media_type": "text/plain",
                        "relative_path": "pod-logs.txt"
                    }]
                }""",
                encoding="utf-8",
            )
            (directory / "pod-logs.txt").write_text(
                "fictional workload restarted after a configuration error\n",
                encoding="utf-8",
            )
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    [
                        "scenario",
                        "prompt",
                        str(directory),
                        "--instruction",
                        "Custom CLI instruction.",
                    ]
                )

        rendered_text = output.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("# Incident Investigation: kubernetes-crashloop-001", rendered_text)
        self.assertIn("Custom CLI instruction.", rendered_text)
        self.assertIn("fictional workload restarted", rendered_text)

    def test_lists_scenario_gallery_without_evidence_content(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            gallery = Path(temporary_directory)
            scenario = gallery / "alpha"
            scenario.mkdir()
            (scenario / "scenario.json").write_text(
                """{
                    "manifest": {
                        "schema_version": "1.0",
                        "scenario_id": "kubernetes-crashloop-001",
                        "title": "Diagnose a fictional CrashLoopBackOff deployment",
                        "category": "kubernetes"
                    },
                    "evidence": [{
                        "artifact_id": "pod-logs.txt",
                        "media_type": "text/plain",
                        "relative_path": "pod-logs.txt"
                    }]
                }""",
                encoding="utf-8",
            )
            (scenario / "pod-logs.txt").write_text(
                "fictional workload restarted after a configuration error\n",
                encoding="utf-8",
            )
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(["scenario", "list", str(gallery)])

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["scenario_count"], 1)
        self.assertEqual(result["scenarios"][0]["scenario_id"], "kubernetes-crashloop-001")
        self.assertEqual(len(result["scenarios"][0]["pack_hash"]), 64)
        self.assertNotIn("evidence", result["scenarios"][0])

    def test_audits_scenario_gallery_without_evidence_content(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            gallery = Path(temporary_directory)
            scenario = gallery / "alpha"
            scenario.mkdir()
            (scenario / "scenario.json").write_text(
                """{
                    "manifest": {
                        "schema_version": "1.0",
                        "scenario_id": "kubernetes-crashloop-001",
                        "title": "Diagnose a fictional CrashLoopBackOff deployment",
                        "category": "kubernetes"
                    },
                    "evidence": [{
                        "artifact_id": "pod-logs.txt",
                        "media_type": "text/plain",
                        "relative_path": "pod-logs.txt"
                    }]
                }""",
                encoding="utf-8",
            )
            (scenario / "pod-logs.txt").write_text(
                "fictional workload restarted after a configuration error\n",
                encoding="utf-8",
            )
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(["scenario", "audit", str(gallery)])

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["audit_passed"])
        self.assertEqual(result["scenario_count"], 1)
        self.assertEqual(result["scenarios"][0]["scenario_id"], "kubernetes-crashloop-001")
        self.assertNotIn("evidence", result["scenarios"][0])

    def test_evaluates_a_local_fictional_response(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            scenario = Path(temporary_directory) / "scenario"
            scenario.mkdir()
            (scenario / "scenario.json").write_text(
                """{
                    "manifest": {
                        "schema_version": "1.0",
                        "scenario_id": "kubernetes-image-reference-001",
                        "title": "Diagnose a fictional image reference failure",
                        "category": "kubernetes"
                    },
                    "evidence": [{
                        "artifact_id": "pod-events.json",
                        "media_type": "application/json",
                        "relative_path": "pod-events.json"
                    }]
                }""",
                encoding="utf-8",
            )
            (scenario / "pod-events.json").write_text("[]\n", encoding="utf-8")
            (scenario / "evaluator.json").write_text(
                """{
                    "scenario_id": "kubernetes-image-reference-001",
                    "diagnosis_rules": [{"rule_id":"image-pull","keyword":"image pull","weight":2}],
                    "permitted_actions": ["correct image reference"],
                    "blocked_action_phrases": ["delete all workloads"]
                }""",
                encoding="utf-8",
            )
            response_path = Path(temporary_directory) / "response.json"
            response_path.write_text(
                """{
                    "scenario_id": "kubernetes-image-reference-001",
                    "analysis": "The image pull failed.",
                    "cited_artifact_ids": ["pod-events.json"],
                    "proposed_actions": ["correct image reference"]
                }""",
                encoding="utf-8",
            )
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(["response", "evaluate", str(scenario), str(response_path)])

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["scenario_id"], "kubernetes-image-reference-001")
        self.assertEqual(result["total"], 8)
        self.assertEqual(result["maximum"], 16)

    def test_doctor_reports_healthy_gallery_and_database(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            gallery = Path(temporary_directory) / "scenarios"
            scenario = gallery / "alpha"
            scenario.mkdir(parents=True)
            (scenario / "scenario.json").write_text(
                '{"manifest":{"schema_version":"1.0","scenario_id":"scenario-001","title":"Fictional scenario","category":"kubernetes"},'
                '"evidence":[{"artifact_id":"logs.txt","media_type":"text/plain","relative_path":"logs.txt"}]}',
                encoding="utf-8",
            )
            (scenario / "logs.txt").write_text("synthetic logs\n", encoding="utf-8")
            db_path = Path(temporary_directory) / "doctor.db"
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(["doctor", "--gallery-path", str(gallery), "--db", str(db_path)])

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["gallery_ok"])
        self.assertEqual(result["scenario_count"], 1)
        self.assertTrue(result["database_ok"])

    def test_doctor_reports_a_missing_gallery_directory(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            missing_gallery = Path(temporary_directory) / "does-not-exist"
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(["doctor", "--gallery-path", str(missing_gallery)])

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(result["status"], "error")
        self.assertFalse(result["gallery_ok"])
        self.assertIn("gallery_error", result)

    def test_doctor_validates_a_backup_archive(self) -> None:
        from opsbench.backup import export_store
        from opsbench.store import SQLiteResultStore

        with TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "backup.json"
            store = SQLiteResultStore()
            try:
                export_store(store, archive_path)
            finally:
                store.close()

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["doctor", "--archive", str(archive_path)])

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["archive_ok"])
        self.assertEqual(result["archive_bundle_count"], 0)
        self.assertEqual(result["archive_schema_version"], "1.0")

    def test_doctor_reports_an_invalid_backup_archive(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "invalid-backup.json"
            archive_path.write_text("not json", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(["doctor", "--archive", str(archive_path)])

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(result["status"], "error")
        self.assertFalse(result["archive_ok"])
        self.assertIn("archive_error", result)

    def test_scaffolds_and_checks_scenario_via_cli(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            scenario_path = Path(temporary_directory) / "kubernetes-test-001"
            init_output = io.StringIO()
            with redirect_stdout(init_output):
                init_exit = main(
                    [
                        "scenario",
                        "init",
                        str(scenario_path),
                        "--id",
                        "kubernetes-test-001",
                        "--title",
                        "Test scenario",
                        "--category",
                        "kubernetes",
                    ]
                )

            self.assertEqual(init_exit, 0)
            init_res = json.loads(init_output.getvalue())
            self.assertEqual(init_res["status"], "scaffolded")
            self.assertEqual(init_res["scenario_id"], "kubernetes-test-001")

            check_output = io.StringIO()
            with redirect_stdout(check_output):
                check_exit = main(["scenario", "check", str(scenario_path)])

            self.assertEqual(check_exit, 0)
            check_res = json.loads(check_output.getvalue())
            self.assertTrue(check_res["passed"])
            self.assertEqual(check_res["issues"], [])

    def test_check_scenario_cli_reports_failure_on_invalid_scenario(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            empty_path = Path(temporary_directory) / "empty"
            empty_path.mkdir()
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["scenario", "check", str(empty_path)])

            self.assertEqual(exit_code, 1)
            result = json.loads(output.getvalue())
            self.assertFalse(result["passed"])
            self.assertTrue(len(result["issues"]) > 0)

    def test_executes_replay_run_and_writes_result_bundle(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            scenario = directory / "scenario"
            scenario.mkdir()
            (scenario / "scenario.json").write_text(
                '{"manifest":{"schema_version":"1.0","scenario_id":"scenario-001","title":"Fictional scenario","category":"kubernetes"},'
                '"evidence":[{"artifact_id":"logs.txt","media_type":"text/plain","relative_path":"logs.txt"}]}',
                encoding="utf-8",
            )
            (scenario / "logs.txt").write_text("synthetic logs\n", encoding="utf-8")
            (scenario / "evaluator.json").write_text(
                '{"scenario_id":"scenario-001","diagnosis_rules":[{"rule_id":"synthetic","keyword":"synthetic","weight":2}],"permitted_actions":["inspect logs"]}',
                encoding="utf-8",
            )
            timeline_path = directory / "timeline.json"
            timeline_path.write_text(
                '{"scenario_id":"scenario-001","initial_symptoms":"Pod degraded","root_cause_analysis":"Synthetic incident rca.",'
                '"steps":[{"step_number":1,"elapsed_seconds":10.0,"event_type":"alert","summary":"synthetic failure detected","artifact_id":"logs.txt"}],'
                '"resolution_actions":["inspect logs"]}',
                encoding="utf-8",
            )
            output_path = directory / "results" / "replay-run.json"
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    [
                        "run",
                        "replay",
                        str(scenario),
                        str(timeline_path),
                        str(output_path),
                        "--run-id",
                        "replay-run-001",
                    ]
                )

            self.assertEqual(exit_code, 0)
            command_result = json.loads(output.getvalue())
            bundle = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(command_result["run"]["runner_kind"], "reliability-replay")
        self.assertEqual(bundle["run"]["runner_kind"], "reliability-replay")
        self.assertEqual(bundle["run"]["model_name"], "reliability-replay-engine")
        self.assertEqual(bundle["report"]["scenario_id"], "scenario-001")
        self.assertIn("matched_rules=synthetic", bundle["report"]["explanation"])
        self.assertIn("missing_citations=none", bundle["report"]["explanation"])

    def test_mcp_cli_commands(self) -> None:
        list_output = io.StringIO()
        with redirect_stdout(list_output):
            list_exit = main(["mcp", "list"])
        self.assertEqual(list_exit, 0)
        list_res = json.loads(list_output.getvalue())
        self.assertEqual(list_res["providers"], ["github", "gitlab", "grafana", "jira", "kubernetes"])

        inspect_output = io.StringIO()
        with redirect_stdout(inspect_output):
            inspect_exit = main(["mcp", "inspect", "jira"])
        self.assertEqual(inspect_exit, 0)
        inspect_res = json.loads(inspect_output.getvalue())
        self.assertEqual(inspect_res["provider"], "jira")
        self.assertGreater(inspect_res["tool_count"], 0)

        missing_output = io.StringIO()
        with redirect_stdout(missing_output):
            missing_exit = main(["mcp", "inspect", "unknown-provider"])
        self.assertEqual(missing_exit, 1)

    def test_scenario_prompt_with_mcp_cli(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            scenario = Path(temporary_directory) / "scenario"
            scenario.mkdir()
            (scenario / "scenario.json").write_text(
                '{"manifest":{"schema_version":"1.0","scenario_id":"scenario-001","title":"Fictional scenario","category":"kubernetes"},'
                '"evidence":[{"artifact_id":"logs.txt","media_type":"text/plain","relative_path":"logs.txt"}]}',
                encoding="utf-8",
            )
            (scenario / "logs.txt").write_text("synthetic logs\n", encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["scenario", "prompt", str(scenario), "--mcp", "jira", "--mcp", "kubernetes"])

            self.assertEqual(exit_code, 0)
            rendered = output.getvalue()
            self.assertIn("## MCP Platform Context", rendered)
            self.assertIn("### Provider: jira", rendered)
            self.assertIn("### Provider: kubernetes", rendered)


if __name__ == "__main__":
    unittest.main()