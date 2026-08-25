from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import unittest

from opsbench.cli import main
from opsbench.scenarios import load_gallery, load_scenario_pack


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_DIRECTORY = REPOSITORY_ROOT / "scenarios"


class FictionalFixtureGalleryTests(unittest.TestCase):
    def test_loads_fictional_image_reference_scenario(self) -> None:
        pack = load_scenario_pack(SCENARIOS_DIRECTORY / "kubernetes-image-reference-001")

        self.assertEqual(pack.manifest.scenario_id, "kubernetes-image-reference-001")
        self.assertEqual(pack.manifest.category, "kubernetes")
        self.assertEqual(len(pack.evidence), 3)
        self.assertEqual(len(pack.content_hash()), 64)

    def test_lists_fixture_through_cli(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(["scenario", "list", str(SCENARIOS_DIRECTORY)])

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["scenario_count"], 1)
        self.assertEqual(result["scenarios"][0]["scenario_id"], "kubernetes-image-reference-001")

    def test_gallery_has_no_duplicate_scenario_ids(self) -> None:
        gallery = load_gallery(SCENARIOS_DIRECTORY)

        self.assertEqual(
            len(gallery.scenarios),
            len({scenario.manifest.scenario_id for scenario in gallery.scenarios}),
        )


if __name__ == "__main__":
    unittest.main()