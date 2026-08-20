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

    def test_rejects_non_string_fields(self) -> None:
        for field_name, value in (
            ("scenario_id", 1),
            ("title", None),
            ("category", ["kubernetes"]),
            ("schema_version", 1.0),
        ):
            manifest_fields = {
                "scenario_id": "kubernetes-crashloop-001",
                "title": "Diagnose a CrashLoopBackOff deployment",
                "category": "kubernetes",
                "schema_version": SUPPORTED_SCHEMA_VERSION,
            }
            manifest_fields[field_name] = value

            with self.subTest(field_name=field_name):
                with self.assertRaisesRegex(ValueError, f"{field_name} must be a string"):
                    ScenarioManifest(**manifest_fields)

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

    def test_serializes_manifest_with_stable_key_order(self) -> None:
        manifest = ScenarioManifest(
            scenario_id="kubernetes-crashloop-001",
            title="Diagnose a CrashLoopBackOff deployment",
            category="kubernetes",
        )

        self.assertEqual(
            manifest.canonical_json(),
            '{"category":"kubernetes","scenario_id":"kubernetes-crashloop-001",'
            '"schema_version":"1.0","title":"Diagnose a CrashLoopBackOff deployment"}',
        )

    def test_hash_is_reproducible_for_equivalent_manifests(self) -> None:
        first_manifest = ScenarioManifest(
            scenario_id="kubernetes-crashloop-001",
            title="Diagnose a CrashLoopBackOff deployment",
            category="kubernetes",
        )
        second_manifest = ScenarioManifest(
            category="kubernetes",
            title="Diagnose a CrashLoopBackOff deployment",
            scenario_id="kubernetes-crashloop-001",
        )

        self.assertEqual(first_manifest.content_hash(), second_manifest.content_hash())
        self.assertEqual(len(first_manifest.content_hash()), 64)

    def test_hash_changes_when_manifest_content_changes(self) -> None:
        original_manifest = ScenarioManifest(
            scenario_id="kubernetes-crashloop-001",
            title="Diagnose a CrashLoopBackOff deployment",
            category="kubernetes",
        )
        changed_manifest = ScenarioManifest(
            scenario_id="kubernetes-crashloop-001",
            title="Diagnose a CrashLoopBackOff deployment",
            category="observability",
        )

        self.assertNotEqual(
            original_manifest.content_hash(), changed_manifest.content_hash()
        )


if __name__ == "__main__":
    unittest.main()