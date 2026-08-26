from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from opsbench.cli import build_parser, main


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

    def test_parses_response_evaluate_command(self) -> None:
        parsed = build_parser().parse_args(
            ["response", "evaluate", "scenarios/example", "responses/example.json"]
        )

        self.assertEqual(parsed.command, "response")
        self.assertEqual(parsed.response_command, "evaluate")
        self.assertEqual(parsed.scenario_path, "scenarios/example")
        self.assertEqual(parsed.response_path, "responses/example.json")

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