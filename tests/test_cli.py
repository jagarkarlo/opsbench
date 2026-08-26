from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from opsbench.cli import build_parser, main
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


if __name__ == "__main__":
    unittest.main()