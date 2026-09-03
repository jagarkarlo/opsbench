"""Local backup and recovery drill orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from opsbench.backup import export_store, restore_archive, verify_archive
from opsbench.store import RunQuery, SQLiteResultStore


@dataclass(frozen=True)
class RecoveryDrillResult:
    """Verified outcome of exporting and restoring a local result store."""

    archive_path: str
    archive_sha256: str
    restored_bundle_hashes: tuple[str, ...]
    restored_count: int
    source_count: int

    def __post_init__(self) -> None:
        if self.source_count < 0 or self.restored_count < 0:
            raise ValueError("bundle counts must be non-negative")
        if self.source_count != self.restored_count:
            raise ValueError("source and restored bundle counts must match")
        if len(self.restored_bundle_hashes) != self.restored_count:
            raise ValueError("restored bundle hash count must match restored_count")

    def to_dict(self) -> dict[str, object]:
        return {
            "archive_path": self.archive_path,
            "archive_sha256": self.archive_sha256,
            "restored_bundle_hashes": list(self.restored_bundle_hashes),
            "restored_count": self.restored_count,
            "source_count": self.source_count,
            "status": "verified",
        }


def run_recovery_drill(
    source_database_path: Path, archive_path: Path, restored_database_path: Path
) -> RecoveryDrillResult:
    """Export a database, restore it into a fresh database, and verify exact bundle hashes."""
    for field_name, path in (
        ("source_database_path", source_database_path),
        ("archive_path", archive_path),
        ("restored_database_path", restored_database_path),
    ):
        if not isinstance(path, Path):
            raise ValueError(f"{field_name} must be a Path")
    if not source_database_path.is_file():
        raise ValueError(f"source database must be a file: {source_database_path}")
    if restored_database_path.exists():
        raise ValueError(f"restored database must not already exist: {restored_database_path}")

    source_store = SQLiteResultStore(source_database_path)
    try:
        source_bundles = source_store.query(RunQuery(limit=2**31 - 1))
        manifest = export_store(source_store, archive_path)
    finally:
        source_store.close()

    archive = verify_archive(archive_path)
    restored_store = SQLiteResultStore(restored_database_path)
    try:
        restore_archive(restored_store, archive)
        restored_bundles = restored_store.query(RunQuery(limit=2**31 - 1))
    finally:
        restored_store.close()

    source_hashes = tuple(sorted(bundle.content_hash() for bundle in source_bundles))
    restored_hashes = tuple(sorted(bundle.content_hash() for bundle in restored_bundles))
    if source_hashes != restored_hashes:
        raise ValueError("restored bundle hashes do not match the source database")

    return RecoveryDrillResult(
        archive_path=str(archive_path),
        archive_sha256=manifest.archive_sha256,
        restored_bundle_hashes=restored_hashes,
        restored_count=len(restored_bundles),
        source_count=len(source_bundles),
    )
