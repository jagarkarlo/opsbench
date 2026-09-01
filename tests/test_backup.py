import unittest

from opsbench.backup import BACKUP_SCHEMA_VERSION, BackupManifest, sha256_bytes


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


if __name__ == "__main__":
    unittest.main()