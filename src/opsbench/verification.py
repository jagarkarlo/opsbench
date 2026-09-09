"""Versioned, offline monitoring-path verification contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


VERIFICATION_SCHEMA_VERSION = "1.0"
MAX_VERIFICATION_BYTES = 2 * 1024 * 1024
MONITORING_STAGE_IDS = (
    "signal_emitted",
    "signal_collected",
    "rule_fired",
    "route_matched",
    "receiver_accepted",
)
STAGE_STATUSES = frozenset({"passed", "failed", "unknown", "not_tested"})
_TESTED_STATUSES = frozenset({"passed", "failed", "unknown"})


def _require_non_empty_string(field_name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _validate_timestamp(field_name: str, value: str) -> None:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field_name} must be an ISO-8601 timestamp") from error


def _validate_stage(stage_id: str) -> None:
    if stage_id not in MONITORING_STAGE_IDS:
        raise ValueError(f"unsupported stage_id: {stage_id!r}")


def _validate_status(status: str) -> None:
    if status not in STAGE_STATUSES:
        raise ValueError(f"unsupported status: {status!r}")


@dataclass(frozen=True)
class VerificationAssertion:
    """One declared expectation for a monitoring path stage."""

    assertion_id: str
    stage_id: str
    description: str

    def __post_init__(self) -> None:
        _require_non_empty_string("assertion_id", self.assertion_id)
        _validate_stage(_require_non_empty_string("stage_id", self.stage_id))
        _require_non_empty_string("description", self.description)

    def to_dict(self) -> dict[str, str]:
        return {
            "assertion_id": self.assertion_id,
            "description": self.description,
            "stage_id": self.stage_id,
        }


@dataclass(frozen=True)
class VerificationObservation:
    """Observed evidence for one monitoring path stage."""

    stage_id: str
    status: str
    observed_at: str | None = None
    evidence_refs: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        _validate_stage(_require_non_empty_string("stage_id", self.stage_id))
        _validate_status(_require_non_empty_string("status", self.status))
        if self.observed_at is not None:
            _validate_timestamp("observed_at", _require_non_empty_string("observed_at", self.observed_at))
        if not isinstance(self.evidence_refs, tuple) or not all(
            isinstance(reference, str) and reference.strip() for reference in self.evidence_refs
        ):
            raise ValueError("evidence_refs must be a tuple of non-empty strings")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("evidence_refs must be unique")
        if not isinstance(self.summary, str):
            raise ValueError("summary must be a string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_refs": list(self.evidence_refs),
            "observed_at": self.observed_at,
            "stage_id": self.stage_id,
            "status": self.status,
            "summary": self.summary,
        }


@dataclass(frozen=True)
class VerificationInput:
    """Declared monitoring-path assertions and supplied observations."""

    verification_id: str
    scenario_id: str
    started_at: str
    assertions: tuple[VerificationAssertion, ...]
    observations: tuple[VerificationObservation, ...]
    schema_version: str = VERIFICATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_non_empty_string("verification_id", self.verification_id)
        _require_non_empty_string("scenario_id", self.scenario_id)
        _validate_timestamp("started_at", _require_non_empty_string("started_at", self.started_at))
        if self.schema_version != VERIFICATION_SCHEMA_VERSION:
            raise ValueError(f"unsupported verification schema_version: {self.schema_version!r}")
        if not isinstance(self.assertions, tuple) or not all(
            isinstance(assertion, VerificationAssertion) for assertion in self.assertions
        ):
            raise ValueError("assertions must be a tuple of VerificationAssertion values")
        if not isinstance(self.observations, tuple) or not all(
            isinstance(observation, VerificationObservation) for observation in self.observations
        ):
            raise ValueError("observations must be a tuple of VerificationObservation values")
        assertion_ids = [assertion.assertion_id for assertion in self.assertions]
        if len(assertion_ids) != len(set(assertion_ids)):
            raise ValueError("assertion_id values must be unique")
        assertion_stages = [assertion.stage_id for assertion in self.assertions]
        if len(assertion_stages) != len(set(assertion_stages)):
            raise ValueError("assertions must declare each stage_id at most once")
        observation_stages = [observation.stage_id for observation in self.observations]
        if len(observation_stages) != len(set(observation_stages)):
            raise ValueError("duplicate stage_id observations are not allowed")
        if any(stage_id not in assertion_stages for stage_id in observation_stages):
            raise ValueError("observations must reference a declared assertion stage_id")

    def to_dict(self) -> dict[str, Any]:
        return {
            "assertions": [assertion.to_dict() for assertion in self.assertions],
            "observations": [observation.to_dict() for observation in self.observations],
            "scenario_id": self.scenario_id,
            "schema_version": self.schema_version,
            "started_at": self.started_at,
            "verification_id": self.verification_id,
        }


@dataclass(frozen=True)
class VerificationCoverage:
    """Measured stage coverage; it does not imply unobserved stages failed."""

    tested_stage_count: int
    total_stage_count: int

    def __post_init__(self) -> None:
        if self.total_stage_count <= 0:
            raise ValueError("total_stage_count must be positive")
        if not 0 <= self.tested_stage_count <= self.total_stage_count:
            raise ValueError("tested_stage_count must be within total_stage_count")

    @property
    def ratio(self) -> float:
        return self.tested_stage_count / self.total_stage_count

    def to_dict(self) -> dict[str, float | int]:
        return {
            "ratio": self.ratio,
            "tested_stage_count": self.tested_stage_count,
            "total_stage_count": self.total_stage_count,
        }


@dataclass(frozen=True)
class VerificationAssertionResult:
    """Resolved status for one declared assertion."""

    assertion_id: str
    stage_id: str
    status: str
    description: str

    def __post_init__(self) -> None:
        _require_non_empty_string("assertion_id", self.assertion_id)
        _validate_stage(_require_non_empty_string("stage_id", self.stage_id))
        _validate_status(_require_non_empty_string("status", self.status))
        _require_non_empty_string("description", self.description)

    def to_dict(self) -> dict[str, str]:
        return {
            "assertion_id": self.assertion_id,
            "description": self.description,
            "stage_id": self.stage_id,
            "status": self.status,
        }


@dataclass(frozen=True)
class VerificationReport:
    """Deterministic verification result with explicit coverage boundaries."""

    verification_id: str
    scenario_id: str
    outcome: str
    coverage: VerificationCoverage
    assertions: tuple[VerificationAssertionResult, ...]
    observations: tuple[VerificationObservation, ...]
    schema_version: str = VERIFICATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_non_empty_string("verification_id", self.verification_id)
        _require_non_empty_string("scenario_id", self.scenario_id)
        if self.outcome not in {"passed", "failed", "unknown"}:
            raise ValueError("outcome must be passed, failed, or unknown")
        if self.schema_version != VERIFICATION_SCHEMA_VERSION:
            raise ValueError(f"unsupported verification schema_version: {self.schema_version!r}")
        if not isinstance(self.coverage, VerificationCoverage):
            raise ValueError("coverage must be a VerificationCoverage")
        if not isinstance(self.assertions, tuple) or not all(
            isinstance(assertion, VerificationAssertionResult) for assertion in self.assertions
        ):
            raise ValueError("assertions must be a tuple of VerificationAssertionResult values")
        if not isinstance(self.observations, tuple) or not all(
            isinstance(observation, VerificationObservation) for observation in self.observations
        ):
            raise ValueError("observations must be a tuple of VerificationObservation values")

    def to_dict(self) -> dict[str, Any]:
        return {
            "assertions": [assertion.to_dict() for assertion in self.assertions],
            "coverage": self.coverage.to_dict(),
            "observations": [observation.to_dict() for observation in self.observations],
            "outcome": self.outcome,
            "scenario_id": self.scenario_id,
            "schema_version": self.schema_version,
            "verification_id": self.verification_id,
        }

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=True, separators=(",", ":"), sort_keys=True)

    def content_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def evaluate_verification(verification_input: VerificationInput) -> VerificationReport:
    """Resolve declared assertions without inferring causes or contacting services."""
    if not isinstance(verification_input, VerificationInput):
        raise ValueError("verification_input must be a VerificationInput")
    observations_by_stage = {observation.stage_id: observation for observation in verification_input.observations}
    assertion_results = tuple(
        VerificationAssertionResult(
            assertion_id=assertion.assertion_id,
            stage_id=assertion.stage_id,
            status=observations_by_stage.get(
                assertion.stage_id,
                VerificationObservation(assertion.stage_id, "not_tested"),
            ).status,
            description=assertion.description,
        )
        for assertion in verification_input.assertions
    )
    statuses = {assertion.status for assertion in assertion_results}
    if "failed" in statuses:
        outcome = "failed"
    elif statuses != {"passed"}:
        outcome = "unknown"
    else:
        outcome = "passed"
    coverage = VerificationCoverage(
        tested_stage_count=sum(
            assertion.status in _TESTED_STATUSES for assertion in assertion_results
        ),
        total_stage_count=len(assertion_results),
    )
    return VerificationReport(
        verification_id=verification_input.verification_id,
        scenario_id=verification_input.scenario_id,
        outcome=outcome,
        coverage=coverage,
        assertions=assertion_results,
        observations=verification_input.observations,
    )


def _decode_json(path: Path) -> dict[str, Any]:
    if not isinstance(path, Path) or not path.is_file():
        raise ValueError(f"verification input must be a file: {path}")
    if path.stat().st_size > MAX_VERIFICATION_BYTES:
        raise ValueError(f"verification input exceeds maximum size of {MAX_VERIFICATION_BYTES} bytes")
    try:
        decoded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"verification input is not valid JSON: {path}") from error
    if not isinstance(decoded, dict):
        raise ValueError("verification input must be a JSON object")
    return decoded


def load_verification_input(path: Path) -> VerificationInput:
    """Load and validate a bounded verification input document."""
    decoded = _decode_json(path)
    expected_fields = {"assertions", "observations", "scenario_id", "schema_version", "started_at", "verification_id"}
    if frozenset(decoded) != expected_fields:
        raise ValueError("verification input fields do not match the schema")
    assertions = decoded["assertions"]
    observations = decoded["observations"]
    if not isinstance(assertions, list) or not isinstance(observations, list):
        raise ValueError("assertions and observations must be JSON arrays")
    try:
        assertion_values = tuple(VerificationAssertion(**value) for value in assertions)
        observation_values = tuple(
            VerificationObservation(
                **{**value, "evidence_refs": tuple(value.get("evidence_refs", []))}
            )
            for value in observations
        )
    except (TypeError, AttributeError) as error:
        raise ValueError("verification input entries must be JSON objects") from error
    return VerificationInput(
        verification_id=decoded["verification_id"],
        scenario_id=decoded["scenario_id"],
        started_at=decoded["started_at"],
        assertions=assertion_values,
        observations=observation_values,
        schema_version=decoded["schema_version"],
    )


def write_verification_report(path: Path, report: VerificationReport) -> None:
    """Write one immutable verification report without replacing an existing file."""
    if not isinstance(path, Path):
        raise ValueError("path must be a Path")
    if not isinstance(report, VerificationReport):
        raise ValueError("report must be a VerificationReport")
    if path.exists():
        raise ValueError(f"verification report already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_verification_report(path: Path) -> VerificationReport:
    """Load and validate a bounded verification report."""
    decoded = _decode_json(path)
    expected_fields = {
        "assertions",
        "coverage",
        "observations",
        "outcome",
        "scenario_id",
        "schema_version",
        "verification_id",
    }
    if frozenset(decoded) != expected_fields:
        raise ValueError("verification report fields do not match the schema")
    assertions = decoded["assertions"]
    coverage = decoded["coverage"]
    observations = decoded["observations"]
    if not isinstance(assertions, list) or not isinstance(coverage, dict) or not isinstance(observations, list):
        raise ValueError("verification report assertions, coverage, and observations have invalid types")
    try:
        assertion_values = tuple(VerificationAssertionResult(**value) for value in assertions)
        observation_values = tuple(
            VerificationObservation(
                **{**value, "evidence_refs": tuple(value.get("evidence_refs", []))}
            )
            for value in observations
        )
        coverage_value = VerificationCoverage(
            tested_stage_count=coverage["tested_stage_count"],
            total_stage_count=coverage["total_stage_count"],
        )
        return VerificationReport(
            verification_id=decoded["verification_id"],
            scenario_id=decoded["scenario_id"],
            outcome=decoded["outcome"],
            coverage=coverage_value,
            assertions=assertion_values,
            observations=observation_values,
            schema_version=decoded["schema_version"],
        )
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("verification report contains invalid values") from error
