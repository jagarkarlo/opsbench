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
        self.assertNotIn("evidence", result["scenarios"][0])


if __name__ == "__main__":
    unittest.main()