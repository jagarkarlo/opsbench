"""Portable performance baselines and regression comparisons."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from opsbench.performance import PerformanceMetrics


@dataclass(frozen=True)
class PerformanceBaseline:
    """Immutable reference measurement for detecting local performance regressions."""

    name: str
    wall_time_seconds: float
    items_processed: int
    created_at_utc: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string")
        if self.wall_time_seconds <= 0:
            raise ValueError("wall_time_seconds must be positive")
        if self.items_processed <= 0:
            raise ValueError("items_processed must be positive")
        try:
            datetime.fromisoformat(self.created_at_utc.replace("Z", "+00:00"))
        except (AttributeError, ValueError) as error:
            raise ValueError("created_at_utc must be an ISO-8601 timestamp") from error

    @classmethod
    def from_metrics(cls, metrics: PerformanceMetrics) -> PerformanceBaseline:
        if not isinstance(metrics, PerformanceMetrics):
            raise ValueError("metrics must be a PerformanceMetrics instance")
        return cls(
            name=metrics.name,
            wall_time_seconds=metrics.wall_time_seconds,
            items_processed=metrics.items_processed,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "items_processed": self.items_processed,
            "name": self.name,
            "created_at_utc": self.created_at_utc,
            "wall_time_seconds": self.wall_time_seconds,
        }


@dataclass(frozen=True)
class PerformanceComparison:
    """Comparison of one measurement against a performance baseline."""

    baseline: PerformanceBaseline
    current: PerformanceMetrics
    threshold_percent: float

    def __post_init__(self) -> None:
        if not isinstance(self.baseline, PerformanceBaseline):
            raise ValueError("baseline must be a PerformanceBaseline instance")
        if not isinstance(self.current, PerformanceMetrics):
            raise ValueError("current must be a PerformanceMetrics instance")
        if self.threshold_percent < 0:
            raise ValueError("threshold_percent must be non-negative")

    def wall_time_change_percent(self) -> float:
        return (
            (self.current.wall_time_seconds - self.baseline.wall_time_seconds)
            / self.baseline.wall_time_seconds
            * 100
        )

    def is_regression(self) -> bool:
        return self.wall_time_change_percent() - self.threshold_percent > 1e-9

    def to_dict(self) -> dict[str, object]:
        return {
            "baseline": self.baseline.to_dict(),
            "current": self.current.to_dict(),
            "is_regression": self.is_regression(),
            "threshold_percent": self.threshold_percent,
            "wall_time_change_percent": self.wall_time_change_percent(),
        }


def write_performance_baseline(path: Path, baseline: PerformanceBaseline) -> None:
    """Write a portable baseline JSON artifact without replacing an existing file."""
    if not isinstance(path, Path):
        raise ValueError("path must be a Path")
    if not isinstance(baseline, PerformanceBaseline):
        raise ValueError("baseline must be a PerformanceBaseline instance")
    if path.exists():
        raise ValueError(f"performance baseline already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(baseline.to_dict(), sort_keys=True) + "\n", encoding="utf-8")


def load_performance_baseline(path: Path) -> PerformanceBaseline:
    """Load a portable performance baseline artifact."""
    if not isinstance(path, Path) or not path.is_file():
        raise ValueError(f"performance baseline must be a file: {path}")
    try:
        decoded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"performance baseline is not valid JSON: {path}") from error
    if not isinstance(decoded, dict) or frozenset(decoded) != {
        "created_at_utc",
        "items_processed",
        "name",
        "wall_time_seconds",
    }:
        raise ValueError("performance baseline fields do not match the baseline schema")
    return PerformanceBaseline(**decoded)
