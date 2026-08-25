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
DESCRIPTOR_FIELDS = frozenset({"manifest", "evidence"})
EVIDENCE_REFERENCE_FIELDS = frozenset({"artifact_id", "media_type", "relative_path"})


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
class EvidenceReference:
    """Validated metadata locating one evidence file within a scenario directory."""

    artifact_id: str
    media_type: str
    relative_path: str

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_id, str) or not self.artifact_id.strip():
            raise ValueError("artifact_id must be a non-empty string")
        if not isinstance(self.media_type, str) or "/" not in self.media_type:
            raise ValueError("media_type must be a MIME type")
        if not isinstance(self.relative_path, str) or not self.relative_path.strip():
            raise ValueError("relative_path must be a non-empty string")

        path = Path(self.relative_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("relative_path must remain inside the scenario directory")
        if len(path.parts) != 1:
            raise ValueError("relative_path must name one evidence file")


@dataclass(frozen=True)
class ScenarioDescriptor:
    """Scenario metadata and evidence references before evidence bytes are loaded."""

    manifest: ScenarioManifest
    evidence: Sequence[EvidenceReference]

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, ScenarioManifest):
            raise ValueError("manifest must be a ScenarioManifest")
        if not isinstance(self.evidence, tuple):
            object.__setattr__(self, "evidence", tuple(self.evidence))
        if not self.evidence:
            raise ValueError("scenario descriptor must contain at least one evidence reference")
        if not all(isinstance(reference, EvidenceReference) for reference in self.evidence):
            raise ValueError("evidence must contain only EvidenceReference values")

        artifact_ids = [reference.artifact_id for reference in self.evidence]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("evidence artifact IDs must be unique")


def load_descriptor(path: Path, *, max_bytes: int = MAX_MANIFEST_BYTES) -> ScenarioDescriptor:
    """Load validated manifest and evidence metadata from one scenario JSON file."""
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if not path.is_file():
        raise ValueError(f"descriptor must be a file: {path}")
    if path.stat().st_size > max_bytes:
        raise ValueError(f"descriptor exceeds maximum size of {max_bytes} bytes")

    try:
        decoded: Any = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"descriptor is not valid JSON: {path}") from error
    if not isinstance(decoded, dict):
        raise ValueError("descriptor root must be a JSON object")

    actual_fields = frozenset(decoded)
    missing_fields = DESCRIPTOR_FIELDS - actual_fields
    if missing_fields:
        raise ValueError(f"descriptor is missing fields: {', '.join(sorted(missing_fields))}")
    unknown_fields = actual_fields - DESCRIPTOR_FIELDS
    if unknown_fields:
        raise ValueError(f"descriptor has unknown fields: {', '.join(sorted(unknown_fields))}")
    if not isinstance(decoded["manifest"], dict):
        raise ValueError("manifest must be a JSON object")
    if not isinstance(decoded["evidence"], list):
        raise ValueError("evidence must be a JSON array")

    manifest_fields = frozenset(decoded["manifest"])
    missing_manifest_fields = MANIFEST_FIELDS - manifest_fields
    if missing_manifest_fields:
        raise ValueError(
            f"manifest is missing fields: {', '.join(sorted(missing_manifest_fields))}"
        )
    unknown_manifest_fields = manifest_fields - MANIFEST_FIELDS
    if unknown_manifest_fields:
        raise ValueError(
            f"manifest has unknown fields: {', '.join(sorted(unknown_manifest_fields))}"
        )

    references: list[EvidenceReference] = []
    for index, evidence in enumerate(decoded["evidence"]):
        if not isinstance(evidence, dict):
            raise ValueError(f"evidence[{index}] must be a JSON object")
        evidence_fields = frozenset(evidence)
        if evidence_fields != EVIDENCE_REFERENCE_FIELDS:
            missing_fields = EVIDENCE_REFERENCE_FIELDS - evidence_fields
            unknown_fields = evidence_fields - EVIDENCE_REFERENCE_FIELDS
            details = []
            if missing_fields:
                details.append(f"missing: {', '.join(sorted(missing_fields))}")
            if unknown_fields:
                details.append(f"unknown: {', '.join(sorted(unknown_fields))}")
            raise ValueError(f"evidence[{index}] fields invalid ({'; '.join(details)})")
        references.append(EvidenceReference(**evidence))

    return ScenarioDescriptor(ScenarioManifest(**decoded["manifest"]), tuple(references))


def load_scenario_pack(directory: Path) -> ScenarioPack:
    """Materialize declared, contained evidence files into a reproducible scenario pack."""
    if not directory.is_dir():
        raise ValueError(f"scenario directory must be a directory: {directory}")

    resolved_directory = directory.resolve()
    descriptor = load_descriptor(resolved_directory / "scenario.json")
    artifacts: list[EvidenceArtifact] = []
    for reference in descriptor.evidence:
        candidate = (resolved_directory / reference.relative_path).resolve()
        if candidate.parent != resolved_directory:
            raise ValueError(f"evidence path escapes scenario directory: {reference.relative_path}")
        if not candidate.is_file():
            raise ValueError(f"evidence file must exist: {reference.relative_path}")
        if candidate.stat().st_size > MAX_EVIDENCE_BYTES:
            raise ValueError(
                f"evidence file exceeds maximum size of {MAX_EVIDENCE_BYTES} bytes: "
                f"{reference.relative_path}"
            )
        artifacts.append(
            EvidenceArtifact(
                artifact_id=reference.artifact_id,
                media_type=reference.media_type,
                content=candidate.read_bytes(),
            )
        )

    return ScenarioPack(descriptor.manifest, tuple(artifacts))


@dataclass(frozen=True)
class ScenarioGallery:
    """Immutable index of scenario directories available to a local benchmark run."""

    scenarios: tuple[ScenarioPack, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.scenarios, tuple) or not all(
            isinstance(scenario, ScenarioPack) for scenario in self.scenarios
        ):
            raise ValueError("scenarios must be a tuple of ScenarioPack values")
        scenario_ids = [scenario.manifest.scenario_id for scenario in self.scenarios]
        if len(scenario_ids) != len(set(scenario_ids)):
            raise ValueError("scenario IDs must be unique")

    def by_id(self, scenario_id: str) -> ScenarioPack:
        """Return one indexed scenario by its stable scenario ID."""
        for scenario in self.scenarios:
            if scenario.manifest.scenario_id == scenario_id:
                return scenario
        raise ValueError(f"scenario not found: {scenario_id}")


def load_gallery(directory: Path) -> ScenarioGallery:
    """Discover complete scenario directories directly below one gallery root."""
    if not directory.is_dir():
        raise ValueError(f"gallery directory must be a directory: {directory}")

    scenarios = []
    for candidate in sorted(directory.iterdir(), key=lambda path: path.name):
        if candidate.is_dir() and (candidate / "scenario.json").is_file():
            scenarios.append(load_scenario_pack(candidate))
    return ScenarioGallery(tuple(scenarios))


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