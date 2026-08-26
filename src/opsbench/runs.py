"""Immutable benchmark run records for reproducible local execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path

from opsbench.scoring import Score, ScoreReport


RUN_SCHEMA_VERSION = "1.0"
MAX_RESULT_BUNDLE_BYTES = 2 * 1024 * 1024


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


@dataclass(frozen=True)
class ResultBundle:
    """Portable immutable record joining a benchmark run to its score report."""

    run: BenchmarkRun
    report: ScoreReport

    def __post_init__(self) -> None:
        if not isinstance(self.run, BenchmarkRun):
            raise ValueError("run must be a BenchmarkRun")
        if not isinstance(self.report, ScoreReport):
            raise ValueError("report must be a ScoreReport")
        if self.run.response_hash != self.report.response_hash:
            raise ValueError("run response_hash must match the score report")

    def to_dict(self) -> dict[str, dict[str, int | str | None]]:
        return {"report": self.report.to_dict(), "run": self.run.to_dict()}

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_dict(), ensure_ascii=True, separators=(",", ":"), sort_keys=True
        )

    def content_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def write_result_bundle(path: Path, bundle: ResultBundle) -> None:
    """Write one immutable result bundle without replacing an existing artifact."""
    if not isinstance(path, Path):
        raise ValueError("path must be a Path")
    if not isinstance(bundle, ResultBundle):
        raise ValueError("bundle must be a ResultBundle")
    if path.exists():
        raise ValueError(f"result bundle already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(bundle.canonical_json() + "\n", encoding="utf-8")


def load_result_bundle(path: Path, *, max_bytes: int = MAX_RESULT_BUNDLE_BYTES) -> ResultBundle:
    """Load and validate one bounded result bundle written by OpsBench."""
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if not path.is_file():
        raise ValueError(f"result bundle must be a file: {path}")
    if path.stat().st_size > max_bytes:
        raise ValueError(f"result bundle exceeds maximum size of {max_bytes} bytes")
    try:
        decoded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"result bundle is not valid JSON: {path}") from error
    if not isinstance(decoded, dict) or frozenset(decoded) != {"run", "report"}:
        raise ValueError("result bundle must contain exactly run and report objects")
    if not isinstance(decoded["run"], dict) or not isinstance(decoded["report"], dict):
        raise ValueError("result bundle run and report must be JSON objects")

    run = BenchmarkRun(**decoded["run"])
    report_fields = decoded["report"]
    expected_report_fields = {
        "actions",
        "diagnosis",
        "evidence",
        "explanation",
        "maximum",
        "response_hash",
        "safety",
        "scenario_id",
        "total",
    }
    if frozenset(report_fields) != expected_report_fields:
        raise ValueError("result bundle report fields do not match the score report schema")
    report = ScoreReport(
        scenario_id=report_fields["scenario_id"],
        response_hash=report_fields["response_hash"],
        diagnosis=Score(report_fields["diagnosis"]),
        evidence=Score(report_fields["evidence"]),
        actions=Score(report_fields["actions"]),
        safety=Score(report_fields["safety"]),
        explanation=report_fields["explanation"],
    )
    if report.total != report_fields["total"] or report.maximum != report_fields["maximum"]:
        raise ValueError("result bundle score totals do not match the score report")
    return ResultBundle(run, report)