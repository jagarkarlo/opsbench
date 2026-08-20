"""Versioned scenario contracts for reproducible OpsBench evaluations."""

from __future__ import annotations

from dataclasses import dataclass


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