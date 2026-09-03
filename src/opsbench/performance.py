"""Performance measurement and profiling utilities for OpsBench scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import time
from typing import Callable, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class PerformanceMetrics:
    """Immutable record of execution performance: duration, peak memory, throughput."""

    name: str
    wall_time_seconds: float
    peak_memory_bytes: int | None = None
    items_processed: int = 1
    timestamp_utc: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string")
        if self.wall_time_seconds <= 0:
            raise ValueError("wall_time_seconds must be positive")
        if self.items_processed <= 0:
            raise ValueError("items_processed must be positive")

        if not self.timestamp_utc:
            object.__setattr__(self, "timestamp_utc", datetime.now(timezone.utc).isoformat())

    def throughput_per_second(self) -> float:
        return self.items_processed / self.wall_time_seconds

    def to_dict(self) -> dict[str, object]:
        return {
            "items_processed": self.items_processed,
            "name": self.name,
            "peak_memory_bytes": self.peak_memory_bytes,
            "throughput_per_second": self.throughput_per_second(),
            "timestamp_utc": self.timestamp_utc,
            "wall_time_seconds": self.wall_time_seconds,
        }


class PerformanceProfiler:
    """Lightweight profiler for measuring scenario execution time and throughput."""

    def __init__(self) -> None:
        self._metrics: list[PerformanceMetrics] = []

    def measure(
        self,
        name: str,
        func: Callable[[], T],
        items_processed: int = 1,
    ) -> T:
        """Measure the execution time of a callable and record it."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string")
        if not callable(func):
            raise TypeError("func must be callable")
        if items_processed <= 0:
            raise ValueError("items_processed must be positive")

        start_time = time.perf_counter()
        result = func()
        elapsed = time.perf_counter() - start_time

        metrics = PerformanceMetrics(
            name=name,
            wall_time_seconds=elapsed,
            items_processed=items_processed,
        )
        self._metrics.append(metrics)
        return result

    def recorded_metrics(self) -> tuple[PerformanceMetrics, ...]:
        return tuple(self._metrics)

    def clear(self) -> None:
        self._metrics.clear()
