import unittest

from opsbench.scenarios import SUPPORTED_SCHEMA_VERSION, ScenarioManifest


class ScenarioManifestTests(unittest.TestCase):
    def test_accepts_a_supported_manifest(self) -> None:
        manifest = ScenarioManifest(
            scenario_id="kubernetes-crashloop-001",
            title="Diagnose a CrashLoopBackOff deployment",
            category="kubernetes",
        )

        self.assertEqual(manifest.schema_version, SUPPORTED_SCHEMA_VERSION)
        self.assertEqual(manifest.category, "kubernetes")

    def test_rejects_unknown_schema_version(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported schema_version"):
            ScenarioManifest(
                scenario_id="kubernetes-crashloop-001",
                title="Diagnose a CrashLoopBackOff deployment",
                category="kubernetes",
                schema_version="2.0",
            )

    def test_rejects_missing_identity_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "scenario_id must not be empty"):
            ScenarioManifest(
                scenario_id=" ",
                title="Valid title",
                category="kubernetes",
            )

        with self.assertRaisesRegex(ValueError, "title must not be empty"):
            ScenarioManifest(
                scenario_id="kubernetes-crashloop-001",
                title=" ",
                category="kubernetes",
            )

    def test_rejects_unknown_category(self) -> None:
        with self.assertRaisesRegex(ValueError, "category must be one of"):
            ScenarioManifest(
                scenario_id="unknown-001",
                title="Unsupported category",
                category="networking",
            )


if __name__ == "__main__":
    unittest.main()