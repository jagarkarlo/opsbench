from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import unittest

from opsbench.cli import main
from opsbench.responses import load_response
from opsbench.scenarios import load_gallery, load_scenario_pack
from opsbench.scoring import evaluate_response, load_evaluator_profile


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_DIRECTORY = REPOSITORY_ROOT / "scenarios"


class FictionalFixtureGalleryTests(unittest.TestCase):
    def test_loads_fictional_latency_scenario(self) -> None:
        pack = load_scenario_pack(SCENARIOS_DIRECTORY / "observability-latency-001")

        self.assertEqual(pack.manifest.scenario_id, "observability-latency-001")
        self.assertEqual(pack.manifest.category, "observability")
        self.assertEqual([artifact.artifact_id for artifact in pack.evidence], [
            "alert.json",
            "metrics.prom",
            "service-logs.txt",
        ])

    def test_loads_fictional_image_reference_scenario(self) -> None:
        pack = load_scenario_pack(SCENARIOS_DIRECTORY / "kubernetes-image-reference-001")

        self.assertEqual(pack.manifest.scenario_id, "kubernetes-image-reference-001")
        self.assertEqual(pack.manifest.category, "kubernetes")
        self.assertEqual(len(pack.evidence), 3)
        self.assertEqual(len(pack.content_hash()), 64)

    def test_fixture_evaluator_profile_matches_scenario(self) -> None:
        directory = SCENARIOS_DIRECTORY / "kubernetes-image-reference-001"
        pack = load_scenario_pack(directory)
        profile = load_evaluator_profile(directory / "evaluator.json")

        self.assertEqual(profile.scenario_id, pack.manifest.scenario_id)
        self.assertEqual(
            [rule.rule_id for rule in profile.diagnosis_rules],
            ["image-pull", "manifest-unknown"],
        )

    def test_reference_response_evaluates_reproducibly(self) -> None:
        directory = SCENARIOS_DIRECTORY / "kubernetes-image-reference-001"
        pack = load_scenario_pack(directory)
        profile = load_evaluator_profile(directory / "evaluator.json")
        response = load_response(directory / "responses" / "reference-response.json")

        first_report = evaluate_response(pack, profile, response)
        second_report = evaluate_response(pack, profile, response)

        self.assertEqual(first_report.content_hash(), second_report.content_hash())
        self.assertEqual(first_report.total, 12)
        self.assertEqual(first_report.maximum, 16)

    def test_lists_fixture_through_cli(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(["scenario", "list", str(SCENARIOS_DIRECTORY)])

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["scenario_count"], 2)
        self.assertEqual(
            [scenario["scenario_id"] for scenario in result["scenarios"]],
            ["kubernetes-image-reference-001", "observability-latency-001"],
        )

    def test_gallery_has_no_duplicate_scenario_ids(self) -> None:
        gallery = load_gallery(SCENARIOS_DIRECTORY)

        self.assertEqual(
            len(gallery.scenarios),
            len({scenario.manifest.scenario_id for scenario in gallery.scenarios}),
        )


if __name__ == "__main__":
    unittest.main()