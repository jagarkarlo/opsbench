"""Versioned scenario contracts for reproducible OpsBench evaluations."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence


SUPPORTED_SCHEMA_VERSION = "1.0"
SUPPORTED_CATEGORIES = frozenset(
    {
        "database",
        "gitops",
        "kubernetes",
        "observability",
        "terraform",
    }
)
MAX_MANIFEST_BYTES = 64 * 1024
MANIFEST_FIELDS = frozenset({"category", "scenario_id", "schema_version", "title"})
MAX_EVIDENCE_BYTES = 512 * 1024


@dataclass(frozen=True)
class ScenarioManifest:
    """Minimal, validated identity for a benchmark scenario."""

    scenario_id: str
    title: str
    category: str
    schema_version: str = SUPPORTED_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for field_name, value in (
            ("scenario_id", self.scenario_id),
            ("title", self.title),
            ("category", self.category),
            ("schema_version", self.schema_version),
        ):
            if not isinstance(value, str):
                raise ValueError(f"{field_name} must be a string")
        if self.schema_version != SUPPORTED_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported schema_version: {self.schema_version!r}; "
                f"expected {SUPPORTED_SCHEMA_VERSION!r}"
            )
        if not self.scenario_id.strip():
            raise ValueError("scenario_id must not be empty")
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if self.category not in SUPPORTED_CATEGORIES:
            supported_categories = ", ".join(sorted(SUPPORTED_CATEGORIES))
            raise ValueError(
                f"category must be one of: {supported_categories}"
            )

    def to_dict(self) -> dict[str, str]:
        """Return the complete schema-owned representation of this manifest."""
        return {
            "category": self.category,
            "scenario_id": self.scenario_id,
            "schema_version": self.schema_version,
            "title": self.title,
        }

    def canonical_json(self) -> str:
        """Serialize the manifest into stable JSON for content-addressed storage."""
        return json.dumps(
            self.to_dict(),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )

    def content_hash(self) -> str:
        """Return the SHA-256 digest of the canonical manifest representation."""
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EvidenceArtifact:
    """Immutable, content-addressed evidence supplied to a benchmark response."""

    artifact_id: str
    media_type: str
    content: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_id, str) or not self.artifact_id.strip():
            raise ValueError("artifact_id must be a non-empty string")
        if "/" in self.artifact_id or "\\" in self.artifact_id:
            raise ValueError("artifact_id must not contain path separators")
        if not isinstance(self.media_type, str) or "/" not in self.media_type:
            raise ValueError("media_type must be a MIME type")
        if not isinstance(self.content, bytes):
            raise ValueError("content must be bytes")
        if len(self.content) > MAX_EVIDENCE_BYTES:
            raise ValueError(f"evidence exceeds maximum size of {MAX_EVIDENCE_BYTES} bytes")

    def content_hash(self) -> str:
        """Return the SHA-256 digest of the original evidence bytes."""
        return hashlib.sha256(self.content).hexdigest()


@dataclass(frozen=True)
class ScenarioPack:
    """Complete immutable input bundle for one reproducible benchmark scenario."""

    manifest: ScenarioManifest
    evidence: Sequence[EvidenceArtifact]

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, ScenarioManifest):
            raise ValueError("manifest must be a ScenarioManifest")
        if not isinstance(self.evidence, tuple):
            object.__setattr__(self, "evidence", tuple(self.evidence))
        if not self.evidence:
            raise ValueError("scenario pack must contain at least one evidence artifact")
        if not all(isinstance(artifact, EvidenceArtifact) for artifact in self.evidence):
            raise ValueError("evidence must contain only EvidenceArtifact values")

        artifact_ids = [artifact.artifact_id for artifact in self.evidence]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("evidence artifact IDs must be unique")

    def canonical_json(self) -> str:
        """Return the stable representation used to identify this complete input bundle."""
        evidence = sorted(
            (
                {
                    "artifact_id": artifact.artifact_id,
                    "content_hash": artifact.content_hash(),
                    "media_type": artifact.media_type,
                }
                for artifact in self.evidence
            ),
            key=lambda artifact: artifact["artifact_id"],
        )
        return json.dumps(
            {
                "evidence": evidence,
                "manifest": self.manifest.to_dict(),
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )

    def content_hash(self) -> str:
        """Return the SHA-256 digest for the manifest and evidence identities."""
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def load_manifest(path: Path, *, max_bytes: int = MAX_MANIFEST_BYTES) -> ScenarioManifest:
    """Load one bounded JSON manifest into the versioned scenario contract."""
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if not path.is_file():
        raise ValueError(f"manifest must be a file: {path}")
    if path.stat().st_size > max_bytes:
        raise ValueError(f"manifest exceeds maximum size of {max_bytes} bytes")

    try:
        decoded: Any = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"manifest is not valid JSON: {path}") from error

    if not isinstance(decoded, dict):
        raise ValueError("manifest root must be a JSON object")

    actual_fields = frozenset(decoded)
    missing_fields = MANIFEST_FIELDS - actual_fields
    if missing_fields:
        raise ValueError(f"manifest is missing fields: {', '.join(sorted(missing_fields))}")

    unknown_fields = actual_fields - MANIFEST_FIELDS
    if unknown_fields:
        raise ValueError(f"manifest has unknown fields: {', '.join(sorted(unknown_fields))}")

    return ScenarioManifest(**decoded)