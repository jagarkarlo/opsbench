import json
import tempfile
import unittest
from pathlib import Path

from opsbench.backup import BACKUP_SCHEMA_VERSION, BackupManifest, VerifiedArchive, sha256_bytes, verify_archive, restore_archive, export_store
from opsbench.store import SQLiteResultStore
from opsbench.runs import BenchmarkRun, ResultBundle
from opsbench.scoring import ScoreReport, Score


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


class RestoreArchiveTests(unittest.TestCase):
    def test_restore_archive_with_empty_bundles(self) -> None:
        """Restoring an empty archive should complete without error."""
        manifest = BackupManifest(sha256_bytes(b"empty"), 0)
        archive = VerifiedArchive(manifest=manifest, bundles=())
        store = SQLiteResultStore()
        
        restore_archive(store, archive)
        
        self.assertEqual(store.count(), 0)

    def test_restore_archive_with_valid_bundle(self) -> None:
        """Restore a valid bundle from archive to the store."""
        run = BenchmarkRun(
            run_id="test-run-1",
            runner_kind="fixture",
            started_at="2026-08-31T12:00:00Z",
            scenario_pack_hash="a" * 64,
            evaluator_profile_hash="b" * 64,
            response_hash="c" * 64,
            model_name="test-model",
        )
        report = ScoreReport(
            scenario_id="test-scenario",
            response_hash="c" * 64,
            diagnosis=Score.GOOD,
            evidence=Score.FULL,
            actions=Score.LOW,
            safety=Score.FULL,
            explanation="Test explanation",
        )
        bundle = ResultBundle(run=run, report=report)
        bundle_dict = bundle.to_dict()
        
        manifest = BackupManifest(sha256_bytes(b"test"), 1)
        archive = VerifiedArchive(manifest=manifest, bundles=(bundle_dict,))
        store = SQLiteResultStore()
        
        restore_archive(store, archive)
        
        self.assertEqual(store.count(), 1)
        restored = store.get("test-run-1")
        self.assertIsNotNone(restored)
        self.assertEqual(restored.run.run_id, "test-run-1")
        self.assertEqual(restored.report.scenario_id, "test-scenario")


class ExportStoreTests(unittest.TestCase):
    def test_export_empty_store(self) -> None:
        """Exporting an empty store should create a valid archive with 0 bundles."""
        store = SQLiteResultStore()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_path = Path(tmpdir) / "archive.json"
            manifest = export_store(store, archive_path)
            
            self.assertTrue(archive_path.exists())
            self.assertEqual(manifest.bundle_count, 0)
            
            # Verify the archive is readable and valid
            verified = verify_archive(archive_path)
            self.assertEqual(verified.bundle_count(), 0)

    def test_export_store_with_bundles(self) -> None:
        """Exporting a store with bundles should create a valid archive."""
        run = BenchmarkRun(
            run_id="export-run-1",
            runner_kind="fixture",
            started_at="2026-08-31T12:00:00Z",
            scenario_pack_hash="a" * 64,
            evaluator_profile_hash="b" * 64,
            response_hash="c" * 64,
            model_name="test-model",
        )
        report = ScoreReport(
            scenario_id="export-scenario",
            response_hash="c" * 64,
            diagnosis=Score.GOOD,
            evidence=Score.FULL,
            actions=Score.LOW,
            safety=Score.FULL,
            explanation="Export test explanation",
        )
        bundle = ResultBundle(run=run, report=report)
        
        store = SQLiteResultStore()
        store.save(bundle)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_path = Path(tmpdir) / "export.json"
            manifest = export_store(store, archive_path)
            
            self.assertTrue(archive_path.exists())
            self.assertEqual(manifest.bundle_count, 1)
            
            # Verify the archive contains the bundle
            verified = verify_archive(archive_path)
            self.assertEqual(verified.bundle_count(), 1)
            self.assertEqual(verified.bundles[0]["run"]["run_id"], "export-run-1")

    def test_export_rejects_existing_path(self) -> None:
        """Exporting to an existing path should raise ValueError."""
        store = SQLiteResultStore()
        
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            with self.assertRaisesRegex(ValueError, "already exists"):
                export_store(store, tmp_path)
        finally:
            Path(tmp_path).unlink()


if __name__ == "__main__":
    unittest.main()

class RestoreConflictTests(unittest.TestCase):
    def test_check_restore_conflicts_with_empty_archive(self) -> None:
        """Restoring an empty archive should have no conflicts."""
        manifest = BackupManifest(sha256_bytes(b"empty"), 0)
        archive = VerifiedArchive(manifest=manifest, bundles=())
        store = SQLiteResultStore()
        
        from opsbench.backup import check_restore_conflicts
        conflicts = check_restore_conflicts(store, archive)
        
        self.assertEqual(conflicts, ())
    
    def test_check_restore_conflicts_with_no_existing_bundles(self) -> None:
        """Restoring to an empty store should have no conflicts."""
        run = BenchmarkRun(
            run_id="new-run-1",
            runner_kind="fixture",
            started_at="2026-08-31T12:00:00Z",
            scenario_pack_hash="a" * 64,
            evaluator_profile_hash="b" * 64,
            response_hash="c" * 64,
            model_name="test-model",
        )
        report = ScoreReport(
            scenario_id="test-scenario",
            response_hash="c" * 64,
            diagnosis=Score.GOOD,
            evidence=Score.FULL,
            actions=Score.LOW,
            safety=Score.FULL,
            explanation="Test explanation",
        )
        bundle = ResultBundle(run=run, report=report)
        
        manifest = BackupManifest(sha256_bytes(b"test"), 1)
        archive = VerifiedArchive(manifest=manifest, bundles=(bundle.to_dict(),))
        store = SQLiteResultStore()
        
        from opsbench.backup import check_restore_conflicts
        conflicts = check_restore_conflicts(store, archive)
        
        self.assertEqual(conflicts, ())
    
    def test_check_restore_conflicts_detects_duplicate_run_id(self) -> None:
        """Restoring an archive with duplicate run_ids should raise ValueError."""
        run = BenchmarkRun(
            run_id="dup-run-1",
            runner_kind="fixture",
            started_at="2026-08-31T12:00:00Z",
            scenario_pack_hash="a" * 64,
            evaluator_profile_hash="b" * 64,
            response_hash="c" * 64,
            model_name="test-model",
        )
        report = ScoreReport(
            scenario_id="test-scenario",
            response_hash="c" * 64,
            diagnosis=Score.GOOD,
            evidence=Score.FULL,
            actions=Score.LOW,
            safety=Score.FULL,
            explanation="Test explanation",
        )
        bundle_dict = ResultBundle(run=run, report=report).to_dict()
        
        # Create archive with the same bundle twice
        manifest = BackupManifest(sha256_bytes(b"dup"), 2)
        archive = VerifiedArchive(manifest=manifest, bundles=(bundle_dict, bundle_dict))
        store = SQLiteResultStore()
        
        from opsbench.backup import check_restore_conflicts
        with self.assertRaisesRegex(ValueError, "duplicate run_ids"):
            check_restore_conflicts(store, archive)
    
    def test_check_restore_conflicts_detects_existing_bundle(self) -> None:
        """Restoring should detect when run_ids already exist in the store."""
        run1 = BenchmarkRun(
            run_id="existing-run-1",
            runner_kind="fixture",
            started_at="2026-08-31T12:00:00Z",
            scenario_pack_hash="a" * 64,
            evaluator_profile_hash="b" * 64,
            response_hash="c" * 64,
            model_name="test-model",
        )
        report1 = ScoreReport(
            scenario_id="test-scenario",
            response_hash="c" * 64,
            diagnosis=Score.GOOD,
            evidence=Score.FULL,
            actions=Score.LOW,
            safety=Score.FULL,
            explanation="Test explanation",
        )
        bundle1 = ResultBundle(run=run1, report=report1)
        
        # Create store with existing bundle
        store = SQLiteResultStore()
        store.save(bundle1)
        
        # Create archive with the same run_id
        run2 = BenchmarkRun(
            run_id="existing-run-1",
            runner_kind="fixture",
            started_at="2026-09-01T12:00:00Z",
            scenario_pack_hash="a" * 64,
            evaluator_profile_hash="b" * 64,
            response_hash="d" * 64,
            model_name="test-model-2",
        )
        report2 = ScoreReport(
            scenario_id="test-scenario",
            response_hash="d" * 64,
            diagnosis=Score.FULL,
            evidence=Score.FULL,
            actions=Score.LOW,
            safety=Score.FULL,
            explanation="Different explanation",
        )
        bundle2 = ResultBundle(run=run2, report=report2)
        
        manifest = BackupManifest(sha256_bytes(b"conflict"), 1)
        archive = VerifiedArchive(manifest=manifest, bundles=(bundle2.to_dict(),))
        
        from opsbench.backup import check_restore_conflicts
        conflicts = check_restore_conflicts(store, archive)
        
        self.assertEqual(conflicts, ("existing-run-1",))
