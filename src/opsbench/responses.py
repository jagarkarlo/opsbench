"""Provider-neutral response contracts for benchmark evaluations."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json


SUPPORTED_RESPONSE_VERSION = "1.0"


@dataclass(frozen=True)
class BenchmarkResponse:
    """A normalized answer submitted for one scenario."""

    scenario_id: str
    analysis: str
    cited_artifact_ids: tuple[str, ...] = ()
    proposed_actions: tuple[str, ...] = ()
    model_name: str | None = None
    adapter_name: str | None = None
    response_version: str = SUPPORTED_RESPONSE_VERSION

    def __post_init__(self) -> None:
        for field_name, value in (
            ("scenario_id", self.scenario_id),
            ("analysis", self.analysis),
            ("response_version", self.response_version),
        ):
            if not isinstance(value, str):
                raise ValueError(f"{field_name} must be a string")
        for field_name, values in (
            ("cited_artifact_ids", self.cited_artifact_ids),
            ("proposed_actions", self.proposed_actions),
        ):
            if not isinstance(values, tuple) or not all(
                isinstance(value, str) for value in values
            ):
                raise ValueError(f"{field_name} must be a tuple of strings")
        for field_name, value in (("model_name", self.model_name), ("adapter_name", self.adapter_name)):
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{field_name} must be a string or None")
        if self.response_version != SUPPORTED_RESPONSE_VERSION:
            raise ValueError(f"unsupported response_version: {self.response_version!r}")
        if not self.scenario_id.strip():
            raise ValueError("scenario_id must not be empty")
        if not self.analysis.strip():
            raise ValueError("analysis must not be empty")
        if len(set(self.cited_artifact_ids)) != len(self.cited_artifact_ids):
            raise ValueError("cited_artifact_ids must be unique")
        if any(not value.strip() for value in self.cited_artifact_ids):
            raise ValueError("cited_artifact_ids must not contain empty values")
        if any(not value.strip() for value in self.proposed_actions):
            raise ValueError("proposed_actions must not contain empty values")

    def to_dict(self) -> dict[str, str | None | list[str]]:
        return {
            "adapter_name": self.adapter_name,
            "analysis": self.analysis,
            "cited_artifact_ids": list(self.cited_artifact_ids),
            "model_name": self.model_name,
            "proposed_actions": list(self.proposed_actions),
            "response_version": self.response_version,
            "scenario_id": self.scenario_id,
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )

    def content_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()