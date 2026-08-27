"""Provider-neutral response contracts for benchmark evaluations."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any


SUPPORTED_RESPONSE_VERSION = "1.0"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
RESPONSE_FIELDS = frozenset(
    {
        "adapter_name",
        "analysis",
        "cited_artifact_ids",
        "model_name",
        "proposed_actions",
        "response_version",
        "scenario_id",
    }
)


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


def parse_response_text(text: str) -> BenchmarkResponse:
    """Parse a raw JSON string (with optional markdown code fencing) into a BenchmarkResponse."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("response text must be a non-empty string")

    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        decoded: Any = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise ValueError(f"response text is not valid JSON: {error}") from error

    if not isinstance(decoded, dict):
        raise ValueError("response root must be a JSON object")
    actual_fields = frozenset(decoded)
    missing_fields = {"analysis", "scenario_id"} - actual_fields
    if missing_fields:
        raise ValueError(f"response is missing fields: {', '.join(sorted(missing_fields))}")
    unknown_fields = actual_fields - RESPONSE_FIELDS
    if unknown_fields:
        raise ValueError(f"response has unknown fields: {', '.join(sorted(unknown_fields))}")

    for field_name in ("cited_artifact_ids", "proposed_actions"):
        if field_name in decoded and not isinstance(decoded[field_name], list):
            raise ValueError(f"{field_name} must be a JSON array")

    decoded["cited_artifact_ids"] = tuple(decoded.get("cited_artifact_ids", []))
    decoded["proposed_actions"] = tuple(decoded.get("proposed_actions", []))
    return BenchmarkResponse(**decoded)


def load_response(path: Path, *, max_bytes: int = MAX_RESPONSE_BYTES) -> BenchmarkResponse:
    """Load one bounded JSON response into the normalized response contract."""
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if not path.is_file():
        raise ValueError(f"response must be a file: {path}")
    if path.stat().st_size > max_bytes:
        raise ValueError(f"response exceeds maximum size of {MAX_RESPONSE_BYTES} bytes")

    return parse_response_text(path.read_text(encoding="utf-8"))