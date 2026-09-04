"""Public benchmark dataset packaging, integrity verification, and distribution."""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from opsbench.scenarios import load_gallery, load_scenario_pack

DATASET_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class PublicDatasetManifest:
    """Metadata and tamper-evident checksums for a published OpsBench scenario dataset."""

    dataset_name: str
    version: str
    created_at_utc: str
    scenario_count: int
    scenarios: tuple[dict[str, Any], ...]
    checksum: str
    schema_version: str = DATASET_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.dataset_name, str) or not self.dataset_name.strip():
            raise ValueError("dataset_name must be a non-empty string")
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("version must be a non-empty string")
        if not isinstance(self.created_at_utc, str) or not self.created_at_utc.strip():
            raise ValueError("created_at_utc must be a non-empty string")
        if not isinstance(self.scenario_count, int) or self.scenario_count < 0:
            raise ValueError("scenario_count must be a non-negative integer")
        if not isinstance(self.scenarios, tuple):
            raise ValueError("scenarios must be a tuple of dicts")
        if not isinstance(self.checksum, str) or len(self.checksum) != 64 or any(
            character not in "0123456789abcdef" for character in self.checksum
        ):
            raise ValueError("checksum must be a 64-character SHA-256 hex digest")
        if self.schema_version != DATASET_SCHEMA_VERSION:
            raise ValueError(f"unsupported dataset schema_version: {self.schema_version!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "checksum": self.checksum,
            "created_at_utc": self.created_at_utc,
            "dataset_name": self.dataset_name,
            "scenario_count": self.scenario_count,
            "scenarios": [dict(s) for s in self.scenarios],
            "schema_version": self.schema_version,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PublicDatasetManifest:
        scenarios = tuple(dict(s) for s in data.get("scenarios", []))
        return cls(
            dataset_name=str(data["dataset_name"]),
            version=str(data["version"]),
            created_at_utc=str(data["created_at_utc"]),
            scenario_count=int(data["scenario_count"]),
            scenarios=scenarios,
            checksum=str(data["checksum"]),
            schema_version=str(data.get("schema_version", DATASET_SCHEMA_VERSION)),
        )


def _compute_dataset_checksum(scenarios_list: list[dict[str, Any]]) -> str:
    """Compute deterministic SHA-256 digest over normalized scenarios entries."""
    canonical_json = json.dumps(scenarios_list, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def export_public_dataset(
    gallery_path: Path | str,
    output_path: Path | str,
    *,
    dataset_name: str = "opsbench-standard",
    version: str = "1.0",
    timestamp_utc: str | None = None,
) -> PublicDatasetManifest:
    """Scan a scenario gallery and serialize a verified public dataset bundle."""
    gal = load_gallery(Path(gallery_path))
    scenarios_meta: list[dict[str, Any]] = []

    for sc in sorted(gal.scenarios, key=lambda s: s.manifest.scenario_id):
        scenarios_meta.append(
            {
                "category": sc.manifest.category,
                "evidence_count": len(sc.evidence),
                "pack_hash": sc.content_hash(),
                "scenario_id": sc.manifest.scenario_id,
                "title": sc.manifest.title,
            }
        )

    checksum = _compute_dataset_checksum(scenarios_meta)
    effective_timestamp = (
        timestamp_utc
        if timestamp_utc is not None
        else datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    manifest = PublicDatasetManifest(
        dataset_name=dataset_name,
        version=version,
        created_at_utc=effective_timestamp,
        scenario_count=len(scenarios_meta),
        scenarios=tuple(scenarios_meta),
        checksum=checksum,
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def load_public_dataset(path: Path | str) -> PublicDatasetManifest:
    """Load a public dataset manifest from a JSON file."""
    p = Path(path)
    if not p.is_file():
        raise ValueError(f"dataset file not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("dataset root must be a JSON object")
    return PublicDatasetManifest.from_dict(data)


def verify_public_dataset(
    dataset_path: Path | str,
    gallery_path: Path | str | None = None,
) -> tuple[bool, list[str]]:
    """Validate a public dataset file's internal checksum and optional agreement with local gallery files."""
    manifest = load_public_dataset(dataset_path)
    issues: list[str] = []

    expected_checksum = _compute_dataset_checksum(list(manifest.scenarios))
    if manifest.checksum != expected_checksum:
        issues.append(f"checksum mismatch: declared {manifest.checksum!r} != computed {expected_checksum!r}")

    if len(manifest.scenarios) != manifest.scenario_count:
        issues.append(
            f"scenario count mismatch: declared {manifest.scenario_count} != actual {len(manifest.scenarios)}"
        )

    if gallery_path is not None:
        gal_dir = Path(gallery_path)
        if not gal_dir.is_dir():
            issues.append(f"gallery directory not found: {gal_dir}")
        else:
            try:
                gallery = load_gallery(gal_dir)
                local_by_id = {s.manifest.scenario_id: s for s in gallery.scenarios}
                for entry in manifest.scenarios:
                    s_id = entry["scenario_id"]
                    if s_id not in local_by_id:
                        issues.append(f"scenario in dataset not found in local gallery: {s_id}")
                    else:
                        local_sc = local_by_id[s_id]
                        if local_sc.content_hash() != entry["pack_hash"]:
                            issues.append(
                                f"pack hash mismatch for {s_id}: local {local_sc.content_hash()!r} "
                                f"!= dataset {entry['pack_hash']!r}"
                            )
            except Exception as error:
                issues.append(f"failed to validate local gallery: {error}")

    return (len(issues) == 0, issues)
