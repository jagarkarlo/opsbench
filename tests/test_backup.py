import json
import tempfile
import unittest
from pathlib import Path

from opsbench.backup import BACKUP_SCHEMA_VERSION, BackupManifest, VerifiedArchive, sha256_bytes, verify_archive


class BackupManifestTests(unittest.TestCase):
    def test_manifest_is_deterministic(self) -> None:
        manifest = BackupManifest(sha256_bytes(b"synthetic archive"), 2)

        self.assertEqual(manifest.schema_version, BACKUP_SCHEMA_VERSION)
        self.assertEqual(
            manifest.canonical_json(),
            '{"archive_sha256":"74a06ea6113b7f98d70ba2286ddaa21a9a17e25ed2bb8736a823dbc46177eb44","bundle_count":2,"schema_version":"1.0"}',
        )

    def test_manifest_rejects_invalid_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            BackupManifest("not-a-digest", 1)
        with self.assertRaisesRegex(ValueError, "non-negative"):
            BackupManifest("a" * 64, -1)


class ArchiveVerificationTests(unittest.TestCase):
    def test_verify_archive_with_valid_content(self) -> None:
        bundles = [{"run_id": "run-1"}, {"run_id": "run-2"}]
        # Create archive with placeholder digest, compute actual digest
        archive_for_digest = {
            "bundles": bundles,
            "manifest": {
                "archive_sha256": "0" * 64,  # placeholder for digest computation
                "bundle_count": 2,
                "schema_version": "1.0",
            },
        }
        archive_bytes = json.dumps(archive_for_digest, separators=(",", ":"), sort_keys=True).encode("utf-8")
        computed_digest = sha256_bytes(archive_bytes)
        
        # Now create the final archive with the computed digest
        archive_json_final = {
            "bundles": bundles,
            "manifest": {
                "archive_sha256": computed_digest,
                "bundle_count": 2,
                "schema_version": "1.0",
            },
        }
        final_bytes = json.dumps(archive_json_final, separators=(",", ":"), sort_keys=True).encode("utf-8")

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp.write(final_bytes)
            tmp_path = tmp.name

        try:
            verified = verify_archive(tmp_path)
            self.assertEqual(verified.manifest.bundle_count, 2)
            self.assertEqual(verified.bundle_count(), 2)
            self.assertEqual(len(verified.bundles), 2)
        finally:
            Path(tmp_path).unlink()

    def test_verify_archive_rejects_digest_mismatch(self) -> None:
        bundles = [{"run_id": "run-1"}]
        archive_json = {
            "manifest": {
                "schema_version": "1.0",
                "bundle_count": 1,
                "archive_sha256": "a" * 64,
            },
            "bundles": bundles,
        }
        archive_bytes = json.dumps(archive_json, separators=(",", ":"), sort_keys=True).encode("utf-8")

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp.write(archive_bytes)
            tmp_path = tmp.name

        try:
            with self.assertRaisesRegex(ValueError, "archive digest mismatch"):
                verify_archive(tmp_path)
        finally:
            Path(tmp_path).unlink()

    def test_verify_archive_rejects_bundle_count_mismatch(self) -> None:
        bundles = [{"run_id": "run-1"}]
        archive_json = {
            "manifest": {
                "schema_version": "1.0",
                "bundle_count": 2,
                "archive_sha256": "a" * 64,
            },
            "bundles": bundles,
        }
        archive_bytes = json.dumps(archive_json, separators=(",", ":"), sort_keys=True).encode("utf-8")

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp.write(archive_bytes)
            tmp_path = tmp.name

        try:
            with self.assertRaisesRegex(ValueError, "bundle count mismatch"):
                verify_archive(tmp_path)
        finally:
            Path(tmp_path).unlink()

    def test_verify_archive_rejects_missing_file(self) -> None:
        with self.assertRaisesRegex(ValueError, "archive file not found"):
            verify_archive("/nonexistent/path/archive.json")


if __name__ == "__main__":
    unittest.main()