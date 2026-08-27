from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from opsbench.validator import lint_scenario

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_DIRECTORY = REPOSITORY_ROOT / "scenarios"


class ScenarioValidatorTests(unittest.TestCase):
    def test_lints_valid_builtin_scenarios(self) -> None:
        for scenario_dir in SCENARIOS_DIRECTORY.iterdir():
            if scenario_dir.is_dir() and (scenario_dir / "scenario.json").is_file():
                issues = lint_scenario(scenario_dir)
                self.assertEqual(issues, [], f"Issues found in {scenario_dir.name}: {issues}")

    def test_detects_missing_manifest_and_evaluator(self) -> None:
        with TemporaryDirectory() as tmpdir:
            empty_dir = Path(tmpdir)
            issues = lint_scenario(empty_dir)
            self.assertIn(f"missing scenario.json in {empty_dir}", issues)

    def test_detects_invalid_manifest_fields(self) -> None:
        with TemporaryDirectory() as tmpdir:
            directory = Path(tmpdir)
            (directory / "scenario.json").write_text(
                '{"manifest":{"schema_version":"0.1","category":"invalid"},"evidence":[]}',
                encoding="utf-8",
            )
            issues = lint_scenario(directory)
            self.assertTrue(any("unsupported schema_version" in msg for msg in issues))
            self.assertTrue(any("unknown scenario category" in msg for msg in issues))


if __name__ == "__main__":
    unittest.main()
