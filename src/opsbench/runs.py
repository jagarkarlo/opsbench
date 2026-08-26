"""Immutable benchmark run records for reproducible local execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json


RUN_SCHEMA_VERSION = "1.0"


def _require_hash(field_name: str, value: str) -> None:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{field_name} must be a SHA-256 hex digest")
    if any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{field_name} must be a SHA-256 hex digest")


@dataclass(frozen=True)
class BenchmarkRun:
    """A content-addressed request to evaluate one response against one scenario."""

    run_id: str
    runner_kind: str
    started_at: str
    scenario_pack_hash: str
    evaluator_profile_hash: str
    response_hash: str
    model_name: str | None = None
    run_schema_version: str = RUN_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for field_name, value in (
            ("run_id", self.run_id),
            ("runner_kind", self.runner_kind),
            ("started_at", self.started_at),
            ("run_schema_version", self.run_schema_version),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        if self.run_schema_version != RUN_SCHEMA_VERSION:
            raise ValueError(f"unsupported run_schema_version: {self.run_schema_version!r}")
        if self.model_name is not None and not isinstance(self.model_name, str):
            raise ValueError("model_name must be a string or None")
        try:
            datetime.fromisoformat(self.started_at.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("started_at must be an ISO-8601 timestamp") from error
        for field_name, value in (
            ("scenario_pack_hash", self.scenario_pack_hash),
            ("evaluator_profile_hash", self.evaluator_profile_hash),
            ("response_hash", self.response_hash),
        ):
            _require_hash(field_name, value)

    def to_dict(self) -> dict[str, str | None]:
        return {
            "evaluator_profile_hash": self.evaluator_profile_hash,
            "model_name": self.model_name,
            "response_hash": self.response_hash,
            "run_id": self.run_id,
            "run_schema_version": self.run_schema_version,
            "runner_kind": self.runner_kind,
            "scenario_pack_hash": self.scenario_pack_hash,
            "started_at": self.started_at,
        }

    def content_hash(self) -> str:
        canonical_json = json.dumps(
            self.to_dict(), ensure_ascii=True, separators=(",", ":"), sort_keys=True
        )
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()