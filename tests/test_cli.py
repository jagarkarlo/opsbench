from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from opsbench.cli import build_parser, main, parse_metadata
from opsbench.runs import BenchmarkRun, ResultBundle, write_result_bundle
from opsbench.scoring import Score, ScoreReport


class CliParserTests(unittest.TestCase):
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
            ]
        )

        self.assertEqual(parsed.command, "run")
        self.assertEqual(parsed.run_command, "openai")
        self.assertEqual(parsed.model, "gpt-4o")
        self.assertEqual(parsed.api_base, "http://localhost:11434/v1")
        self.assertEqual(parsed.run_id, "openai-run-001")

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
                        "fixture-run-001",
                    ]
                )

            command_result = json.loads(output.getvalue())
            bundle = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(command_result["run"]["run_id"], "fixture-run-001")
        self.assertEqual(command_result["report"]["total"], 8)
        self.assertEqual(bundle["run"]["model_name"], "fixture-model")
        self.assertEqual(bundle["run"]["metadata"], {})
        self.assertEqual(len(command_result["bundle_hash"]), 64)

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


if __name__ == "__main__":
    unittest.main()