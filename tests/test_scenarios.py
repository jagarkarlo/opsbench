from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from opsbench.scenarios import (
    MAX_EVIDENCE_BYTES,
    SUPPORTED_SCHEMA_VERSION,
    EvidenceArtifact,
    EvidenceReference,
    ScenarioManifest,
    ScenarioDescriptor,
    ScenarioGallery,
    ScenarioPack,
    load_descriptor,
    load_manifest,
    load_gallery,
    load_scenario_pack,
)


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


class LoadManifestTests(unittest.TestCase):
    def write_manifest(self, directory: Path, content: str) -> Path:
        path = directory / "scenario.json"
        path.write_text(content, encoding="utf-8")
        return path

    def test_loads_valid_manifest(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            manifest_path = self.write_manifest(
                Path(temporary_directory),
                """{
                    "schema_version": "1.0",
                    "scenario_id": "kubernetes-crashloop-001",
                    "title": "Diagnose a CrashLoopBackOff deployment",
                    "category": "kubernetes"
                }""",
            )

            manifest = load_manifest(manifest_path)

        self.assertEqual(manifest.scenario_id, "kubernetes-crashloop-001")

    def test_rejects_invalid_json_and_non_object_roots(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            invalid_json_path = self.write_manifest(directory, "not-json")
            with self.assertRaisesRegex(ValueError, "manifest is not valid JSON"):
                load_manifest(invalid_json_path)

            list_path = self.write_manifest(directory, "[]")
            with self.assertRaisesRegex(ValueError, "manifest root must be a JSON object"):
                load_manifest(list_path)

    def test_rejects_missing_and_unknown_fields(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            missing_field_path = self.write_manifest(
                directory,
                '{"schema_version":"1.0","scenario_id":"example-001",'
                '"title":"Example"}',
            )
            with self.assertRaisesRegex(ValueError, "manifest is missing fields: category"):
                load_manifest(missing_field_path)

            unknown_field_path = self.write_manifest(
                directory,
                '{"schema_version":"1.0","scenario_id":"example-001",'
                '"title":"Example","category":"kubernetes","extra":true}',
            )
            with self.assertRaisesRegex(ValueError, "manifest has unknown fields"):
                load_manifest(unknown_field_path)

    def test_rejects_oversized_or_missing_files(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            oversized_path = self.write_manifest(directory, "{" + '"x":' + '"' + "a" * 100 + '"}')
            with self.assertRaisesRegex(ValueError, "manifest exceeds maximum size"):
                load_manifest(oversized_path, max_bytes=16)

            with self.assertRaisesRegex(ValueError, "manifest must be a file"):
                load_manifest(directory / "missing.json")


class EvidenceArtifactTests(unittest.TestCase):
    def test_hashes_evidence_bytes_deterministically(self) -> None:
        artifact = EvidenceArtifact(
            artifact_id="pod-logs.txt",
            media_type="text/plain",
            content=b"container exited with status 1\n",
        )

        self.assertEqual(
            artifact.content_hash(),
            "fc6876f1a5c354c8290662f762c836eb4b2ba161751d32b9bd5c0990550cea54",
        )

    def test_rejects_unsafe_or_invalid_artifacts(self) -> None:
        cases = (
            (
                {"artifact_id": "", "media_type": "text/plain", "content": b"valid"},
                "artifact_id must be a non-empty string",
            ),
            (
                {"artifact_id": "../secret", "media_type": "text/plain", "content": b"valid"},
                "artifact_id must not contain path separators",
            ),
            (
                {"artifact_id": "logs.txt", "media_type": "text", "content": b"valid"},
                "media_type must be a MIME type",
            ),
            (
                {"artifact_id": "logs.txt", "media_type": "text/plain", "content": "valid"},
                "content must be bytes",
            ),
        )

        for fields, error_message in cases:
            with self.subTest(fields=fields):
                with self.assertRaisesRegex(ValueError, error_message):
                    EvidenceArtifact(**fields)

    def test_rejects_oversized_evidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "evidence exceeds maximum size"):
            EvidenceArtifact(
                artifact_id="logs.txt",
                media_type="text/plain",
                content=b"a" * (MAX_EVIDENCE_BYTES + 1),
            )


class EvidenceReferenceTests(unittest.TestCase):
    def test_accepts_a_single_safe_evidence_file_reference(self) -> None:
        reference = EvidenceReference(
            artifact_id="pod-logs.txt",
            media_type="text/plain",
            relative_path="pod-logs.txt",
        )

        self.assertEqual(reference.relative_path, "pod-logs.txt")

    def test_rejects_unsafe_or_invalid_paths(self) -> None:
        cases = (
            ("", "relative_path must be a non-empty string"),
            ("../private.txt", "relative_path must remain inside the scenario directory"),
            ("evidence/pod-logs.txt", "relative_path must name one evidence file"),
            ("/etc/passwd", "relative_path must remain inside the scenario directory"),
        )

        for relative_path, error_message in cases:
            with self.subTest(relative_path=relative_path):
                with self.assertRaisesRegex(ValueError, error_message):
                    EvidenceReference(
                        artifact_id="pod-logs.txt",
                        media_type="text/plain",
                        relative_path=relative_path,
                    )


class ScenarioDescriptorTests(unittest.TestCase):
    def build_manifest(self) -> ScenarioManifest:
        return ScenarioManifest(
            scenario_id="kubernetes-crashloop-001",
            title="Diagnose a fictional CrashLoopBackOff deployment",
            category="kubernetes",
        )

    def test_accepts_non_empty_unique_evidence_references(self) -> None:
        descriptor = ScenarioDescriptor(
            self.build_manifest(),
            (
                EvidenceReference("pod-logs.txt", "text/plain", "pod-logs.txt"),
                EvidenceReference("deployment.yaml", "application/yaml", "deployment.yaml"),
            ),
        )

        self.assertEqual(len(descriptor.evidence), 2)

    def test_rejects_empty_duplicate_or_invalid_references(self) -> None:
        reference = EvidenceReference("pod-logs.txt", "text/plain", "pod-logs.txt")

        with self.assertRaisesRegex(ValueError, "at least one evidence reference"):
            ScenarioDescriptor(self.build_manifest(), ())
        with self.assertRaisesRegex(ValueError, "artifact IDs must be unique"):
            ScenarioDescriptor(self.build_manifest(), (reference, reference))
        with self.assertRaisesRegex(ValueError, "only EvidenceReference values"):
            ScenarioDescriptor(self.build_manifest(), ("invalid",))


class LoadDescriptorTests(unittest.TestCase):
    def write_descriptor(self, directory: Path, content: str) -> Path:
        path = directory / "scenario.json"
        path.write_text(content, encoding="utf-8")
        return path

    def test_loads_manifest_and_evidence_metadata(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            path = self.write_descriptor(
                Path(temporary_directory),
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
            )

            descriptor = load_descriptor(path)

        self.assertEqual(descriptor.manifest.scenario_id, "kubernetes-crashloop-001")
        self.assertEqual(descriptor.evidence[0].artifact_id, "pod-logs.txt")

    def test_rejects_invalid_root_and_evidence_shapes(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            missing_path = self.write_descriptor(directory, '{"manifest":{}}')
            with self.assertRaisesRegex(ValueError, "descriptor is missing fields: evidence"):
                load_descriptor(missing_path)

            invalid_evidence_path = self.write_descriptor(
                directory,
                '{"manifest":{"schema_version":"1.0","scenario_id":"example-001",'
                '"title":"Example","category":"kubernetes"},"evidence":["logs.txt"]}',
            )
            with self.assertRaisesRegex(ValueError, r"evidence\[0\] must be a JSON object"):
                load_descriptor(invalid_evidence_path)

    def test_rejects_invalid_evidence_fields(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            path = self.write_descriptor(
                Path(temporary_directory),
                '{"manifest":{"schema_version":"1.0","scenario_id":"example-001",'
                '"title":"Example","category":"kubernetes"},"evidence":[{'
                '"artifact_id":"logs.txt","media_type":"text/plain","extra":true}]}',
            )

            with self.assertRaisesRegex(
                ValueError,
                r"evidence\[0\] fields invalid \(missing: relative_path; unknown: extra\)",
            ):
                load_descriptor(path)


class LoadScenarioPackTests(unittest.TestCase):
    def write_descriptor(self, directory: Path, evidence_path: str = "pod-logs.txt") -> None:
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
                    "relative_path": "%s"
                }]
            }""" % evidence_path,
            encoding="utf-8",
        )

    def test_materializes_declared_evidence_into_a_pack(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            self.write_descriptor(directory)
            (directory / "pod-logs.txt").write_text(
                "container restarted after a fictional configuration error\n",
                encoding="utf-8",
            )

            pack = load_scenario_pack(directory)

        self.assertEqual(pack.manifest.scenario_id, "kubernetes-crashloop-001")
        self.assertEqual(pack.evidence[0].content, b"container restarted after a fictional configuration error\n")

    def test_rejects_missing_directory_or_evidence_file(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            with self.assertRaisesRegex(ValueError, "scenario directory must be a directory"):
                load_scenario_pack(directory / "missing")

            self.write_descriptor(directory)
            with self.assertRaisesRegex(ValueError, "evidence file must exist: pod-logs.txt"):
                load_scenario_pack(directory)

    def test_rejects_symlinked_evidence_outside_directory(self) -> None:
        with TemporaryDirectory() as temporary_directory, TemporaryDirectory() as outside_directory:
            directory = Path(temporary_directory)
            outside_file = Path(outside_directory) / "outside.txt"
            outside_file.write_text("private data must not be loaded\n", encoding="utf-8")
            self.write_descriptor(directory)
            (directory / "pod-logs.txt").symlink_to(outside_file)

            with self.assertRaisesRegex(ValueError, "evidence path escapes scenario directory"):
                load_scenario_pack(directory)


class ScenarioGalleryTests(unittest.TestCase):
    def write_scenario(self, gallery: Path, name: str, scenario_id: str) -> None:
        directory = gallery / name
        directory.mkdir()
        (directory / "scenario.json").write_text(
            """{
                "manifest": {
                    "schema_version": "1.0",
                    "scenario_id": "%s",
                    "title": "Diagnose a fictional service restart",
                    "category": "kubernetes"
                },
                "evidence": [{
                    "artifact_id": "pod-logs.txt",
                    "media_type": "text/plain",
                    "relative_path": "pod-logs.txt"
                }]
            }""" % scenario_id,
            encoding="utf-8",
        )
        (directory / "pod-logs.txt").write_text(
            "fictional workload restarted after a configuration error\n",
            encoding="utf-8",
        )

    def test_discovers_direct_scenario_directories_in_stable_order(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            gallery = Path(temporary_directory)
            self.write_scenario(gallery, "zeta", "scenario-zeta")
            self.write_scenario(gallery, "alpha", "scenario-alpha")
            (gallery / "notes.txt").write_text("not a scenario", encoding="utf-8")

            loaded_gallery = load_gallery(gallery)

        self.assertEqual(
            [scenario.manifest.scenario_id for scenario in loaded_gallery.scenarios],
            ["scenario-alpha", "scenario-zeta"],
        )
        self.assertEqual(loaded_gallery.by_id("scenario-zeta").manifest.title, "Diagnose a fictional service restart")

    def test_rejects_missing_gallery_and_duplicate_ids(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            gallery = Path(temporary_directory)
            with self.assertRaisesRegex(ValueError, "gallery directory must be a directory"):
                load_gallery(gallery / "missing")

            self.write_scenario(gallery, "first", "duplicate-scenario")
            self.write_scenario(gallery, "second", "duplicate-scenario")
            with self.assertRaisesRegex(ValueError, "scenario IDs must be unique"):
                load_gallery(gallery)

        with self.assertRaisesRegex(ValueError, "scenario not found"):
            ScenarioGallery(()).by_id("missing-scenario")


class ScenarioPackTests(unittest.TestCase):
    def build_manifest(self) -> ScenarioManifest:
        return ScenarioManifest(
            scenario_id="kubernetes-crashloop-001",
            title="Diagnose a CrashLoopBackOff deployment",
            category="kubernetes",
        )

    def test_pack_hash_is_independent_of_evidence_input_order(self) -> None:
        logs = EvidenceArtifact("pod-logs.txt", "text/plain", b"exit status 1\n")
        manifest = EvidenceArtifact("deployment.yaml", "application/yaml", b"kind: Deployment\n")

        first_pack = ScenarioPack(self.build_manifest(), (logs, manifest))
        second_pack = ScenarioPack(self.build_manifest(), (manifest, logs))

        self.assertEqual(first_pack.content_hash(), second_pack.content_hash())

    def test_pack_rejects_invalid_evidence_collections(self) -> None:
        manifest = self.build_manifest()
        artifact = EvidenceArtifact("pod-logs.txt", "text/plain", b"exit status 1\n")

        with self.assertRaisesRegex(ValueError, "at least one evidence artifact"):
            ScenarioPack(manifest, ())

        with self.assertRaisesRegex(ValueError, "artifact IDs must be unique"):
            ScenarioPack(manifest, (artifact, artifact))

        with self.assertRaisesRegex(ValueError, "only EvidenceArtifact values"):
            ScenarioPack(manifest, ("not-an-artifact",))


if __name__ == "__main__":
    unittest.main()