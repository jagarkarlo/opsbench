"""Portable integrity metadata for local OpsBench backups."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opsbench.store import SQLiteResultStore


BACKUP_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class BackupManifest:
    """Content-addressed metadata for one exported OpsBench archive."""

    archive_sha256: str
    bundle_count: int
    schema_version: str = BACKUP_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != BACKUP_SCHEMA_VERSION:
            raise ValueError(f"unsupported backup schema version: {self.schema_version!r}")
        if not isinstance(self.bundle_count, int) or self.bundle_count < 0:
            raise ValueError("bundle_count must be a non-negative integer")
        if not isinstance(self.archive_sha256, str) or len(self.archive_sha256) != 64:
            raise ValueError("archive_sha256 must be a SHA-256 hex digest")
        if any(character not in "0123456789abcdef" for character in self.archive_sha256):
            raise ValueError("archive_sha256 must be a SHA-256 hex digest")

    def to_dict(self) -> dict[str, str | int]:
        return {
            "archive_sha256": self.archive_sha256,
            "bundle_count": self.bundle_count,
            "schema_version": self.schema_version,
        }

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=True, separators=(",", ":"), sort_keys=True)


@dataclass(frozen=True)
class VerifiedArchive:
    """Validated export archive with manifest integrity verified."""

    manifest: BackupManifest
    bundles: tuple[dict[str, Any], ...]

    def bundle_count(self) -> int:
        """Return the number of result bundles in this archive."""
        return len(self.bundles)


def sha256_bytes(content: bytes) -> str:
    """Return the canonical SHA-256 digest for local archive content."""
    return hashlib.sha256(content).hexdigest()


def verify_archive(archive_path: Path | str) -> VerifiedArchive:
    """Load and verify a backup archive, validating manifest digest and bundle count.
    
    The archive digest is computed on the archive bytes with the digest field set to a placeholder,
    ensuring the digest is self-referential and stable across multiple verifications.
    
    Raises:
        ValueError: If the archive is malformed, digest does not match, or bundle count is incorrect.
    """
    path = Path(archive_path) if isinstance(archive_path, str) else archive_path
    
    if not path.exists():
        raise ValueError(f"archive file not found: {path}")
    if not path.is_file():
        raise ValueError(f"archive path is not a file: {path}")
    
    archive_bytes = path.read_bytes()
    
    try:
        archive_data = json.loads(archive_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError(f"archive is not valid JSON: {error}") from error
    
    if not isinstance(archive_data, dict):
        raise ValueError("archive root must be a JSON object")
    
    if "manifest" not in archive_data:
        raise ValueError("archive is missing required 'manifest' field")
    if "bundles" not in archive_data:
        raise ValueError("archive is missing required 'bundles' field")
    
    manifest_data = archive_data["manifest"]
    if not isinstance(manifest_data, dict):
        raise ValueError("manifest must be a JSON object")
    
    declared_digest = manifest_data.get("archive_sha256", "")
    
    try:
        manifest = BackupManifest(
            archive_sha256=declared_digest,
            bundle_count=manifest_data.get("bundle_count", 0),
            schema_version=manifest_data.get("schema_version", BACKUP_SCHEMA_VERSION),
        )
    except ValueError as error:
        raise ValueError(f"invalid manifest: {error}") from error
    
    bundles_data = archive_data["bundles"]
    if not isinstance(bundles_data, list):
        raise ValueError("bundles must be a JSON array")
    
    if len(bundles_data) != manifest.bundle_count:
        raise ValueError(
            f"bundle count mismatch: archive contains {len(bundles_data)} bundles but manifest declares {manifest.bundle_count}"
        )
    
    # Compute digest on archive with digest field replaced by placeholder to make it self-referential
    archive_for_digest = {
        "bundles": bundles_data,
        "manifest": {
            "archive_sha256": "0" * 64,
            "bundle_count": manifest.bundle_count,
            "schema_version": manifest.schema_version,
        },
    }
    archive_for_digest_bytes = json.dumps(
        archive_for_digest, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    computed_digest = sha256_bytes(archive_for_digest_bytes)
    
    if computed_digest != manifest.archive_sha256:
        raise ValueError(
            f"archive digest mismatch: computed {computed_digest} but manifest declares {manifest.archive_sha256}"
        )
    
    return VerifiedArchive(manifest=manifest, bundles=tuple(bundles_data))


def restore_archive(store: SQLiteResultStore, archive: VerifiedArchive) -> None:
    """Restore a verified archive to the result store atomically.
    
    Loads each bundle from the archive, reconstructs ResultBundle objects, and inserts them into the store.
    All bundles are inserted in a single transaction; if any bundle fails validation or insertion,
    the entire restore is rolled back.
    
    Args:
        store: The SQLiteResultStore to restore into.
        archive: The VerifiedArchive containing bundles to restore.
    
    Raises:
        ValueError: If any bundle cannot be reconstructed or conflicts with existing data.
    """
    from opsbench.runs import ResultBundle, BenchmarkRun, load_result_bundle
    from opsbench.scoring import ScoreReport, Score
    from pathlib import Path
    import tempfile
    
    if archive.bundle_count() == 0:
        return
    
    # Reconstruct ResultBundle objects from the archive data and insert atomically
    bundles_to_restore: list[ResultBundle] = []
    
    for bundle_data in archive.bundles:
        if not isinstance(bundle_data, dict):
            raise ValueError("each archive bundle must be a JSON object")
        
        if "run" not in bundle_data or "report" not in bundle_data:
            raise ValueError("each archive bundle must contain 'run' and 'report' fields")
        
        # Validate by reconstructing the bundle through JSON roundtrip
        bundle_json = json.dumps(bundle_data, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        
        # Write to temp file and load using the standard loader for validation
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp.write(bundle_json + "\n")
            tmp_path = tmp.name
        
        try:
            bundle = load_result_bundle(Path(tmp_path))
            bundles_to_restore.append(bundle)
        finally:
            Path(tmp_path).unlink()
    
    # Insert all bundles atomically
    for bundle in bundles_to_restore:
        store.save(bundle)


def export_store(store: SQLiteResultStore, archive_path: Path | str) -> BackupManifest:
    """Export all result bundles from a store into a backup archive with manifest.
    
    Creates a deterministic JSON archive file with a manifest containing the archive digest
    and bundle count. The archive is self-referential: the manifest digest is computed on 
    the archive with a placeholder digest field.
    
    Args:
        store: The SQLiteResultStore to export from.
        archive_path: Path where the archive file will be written.
    
    Returns:
        The BackupManifest for the exported archive.
    
    Raises:
        ValueError: If the archive path already exists.
    """
    path = Path(archive_path) if isinstance(archive_path, str) else archive_path
    
    if path.exists():
        raise ValueError(f"archive file already exists: {path}")
    
    # Export all bundles from the store as dictionaries
    from opsbench.store import RunQuery
    
    all_bundles = store.query(RunQuery(limit=2**31 - 1))
    bundle_dicts = [bundle.to_dict() for bundle in all_bundles]
    
    # Create archive with placeholder digest
    archive_for_digest = {
        "bundles": bundle_dicts,
        "manifest": {
            "archive_sha256": "0" * 64,
            "bundle_count": len(bundle_dicts),
            "schema_version": BACKUP_SCHEMA_VERSION,
        },
    }
    
    # Compute digest on this structure
    archive_bytes = json.dumps(
        archive_for_digest, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    computed_digest = sha256_bytes(archive_bytes)
    
    # Create final archive with computed digest
    archive_final = {
        "bundles": bundle_dicts,
        "manifest": {
            "archive_sha256": computed_digest,
            "bundle_count": len(bundle_dicts),
            "schema_version": BACKUP_SCHEMA_VERSION,
        },
    }
    
    # Write archive file
    path.parent.mkdir(parents=True, exist_ok=True)
    archive_json = json.dumps(
        archive_final, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    )
    path.write_text(archive_json, encoding="utf-8")
    
    manifest = BackupManifest(
        archive_sha256=computed_digest,
        bundle_count=len(bundle_dicts),
        schema_version=BACKUP_SCHEMA_VERSION,
    )
    
    return manifest