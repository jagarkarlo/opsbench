"""Versioned scenario contracts for reproducible OpsBench evaluations."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json


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