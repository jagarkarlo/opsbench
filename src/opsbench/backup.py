"""Portable integrity metadata for local OpsBench backups."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json


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


def sha256_bytes(content: bytes) -> str:
    """Return the canonical SHA-256 digest for local archive content."""
    return hashlib.sha256(content).hexdigest()