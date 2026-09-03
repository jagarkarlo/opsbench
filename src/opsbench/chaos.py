"""Bounded local load and synthetic chaos matrix execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from opsbench.adapters import GalleryFixtureResponseAdapter
from opsbench.failure_injection import FailureInjection, FailureInjectingAdapter, FailureMode
from opsbench.responses import BenchmarkResponse, load_response
from opsbench.runner import SuiteExecution, execute_suite_resilient


@dataclass(frozen=True)
class ChaosCaseResult:
    """One repeated synthetic failure-mode case."""

    iteration: int
    mode: FailureMode
    execution: SuiteExecution

    def to_dict(self) -> dict[str, object]:
        return {
            "bundle_count": len(self.execution.bundles),
            "failure_count": len(self.execution.failures),
            "failures": [failure.to_dict() for failure in self.execution.failures],
            "iteration": self.iteration,
            "mode": self.mode.value,
            "scenario_count": self.execution.scenario_count,
            "status": "completed_with_injected_failures"
            if self.execution.failures
            else "success",
        }


@dataclass(frozen=True)
class ChaosMatrixResult:
    """Deterministic aggregate for a bounded local load/chaos matrix."""

    cases: tuple[ChaosCaseResult, ...]
    iterations: int
    modes: tuple[FailureMode, ...]

    def __post_init__(self) -> None:
        if self.iterations <= 0:
            raise ValueError("iterations must be positive")
        if not self.modes or len(set(self.modes)) != len(self.modes):
            raise ValueError("modes must contain at least one unique FailureMode")
        if len(self.cases) != self.iterations * len(self.modes):
            raise ValueError("case count must match iterations and modes")

    @property
    def failure_count(self) -> int:
        return sum(len(case.execution.failures) for case in self.cases)

    def to_dict(self) -> dict[str, object]:
        return {
            "case_count": len(self.cases),
            "cases": [case.to_dict() for case in self.cases],
            "failure_count": self.failure_count,
            "iterations": self.iterations,
            "modes": [mode.value for mode in self.modes],
            "status": "completed_with_injected_failures"
            if self.failure_count
            else "success",
        }


def run_chaos_matrix(
    gallery_directory: Path,
    output_directory: Path,
    *,
    iterations: int = 1,
    modes: tuple[FailureMode, ...] = tuple(FailureMode),
    scenario_ids: tuple[str, ...] = (),
    max_workers: int = 1,
) -> ChaosMatrixResult:
    """Run a bounded fixture load matrix using only synthetic failure injection."""
    if not isinstance(gallery_directory, Path) or not gallery_directory.is_dir():
        raise ValueError(f"gallery_directory must be a directory: {gallery_directory}")
    if not isinstance(output_directory, Path):
        raise ValueError("output_directory must be a Path")
    if not isinstance(iterations, int) or isinstance(iterations, bool) or iterations <= 0:
        raise ValueError("iterations must be a positive integer")
    if not isinstance(modes, tuple) or not modes or not all(isinstance(mode, FailureMode) for mode in modes):
        raise ValueError("modes must be a non-empty tuple of FailureMode values")
    if len(set(modes)) != len(modes):
        raise ValueError("modes must be unique")
    if not isinstance(max_workers, int) or isinstance(max_workers, bool) or max_workers <= 0:
        raise ValueError("max_workers must be a positive integer")

    responses: dict[str, BenchmarkResponse] = {}
    for candidate in sorted(gallery_directory.iterdir(), key=lambda path: path.name):
        if candidate.is_dir() and (candidate / "scenario.json").is_file():
            response_path = candidate / "responses" / "reference-response.json"
            if not response_path.is_file():
                raise ValueError(f"scenario missing reference response: {candidate}")
            response = load_response(response_path)
            responses[response.scenario_id] = response
    if not responses:
        raise ValueError(f"no scenario packs found in gallery directory: {gallery_directory}")

    cases: list[ChaosCaseResult] = []
    for iteration in range(1, iterations + 1):
        for mode in modes:
            adapter = FailureInjectingAdapter(
                GalleryFixtureResponseAdapter(responses),
                FailureInjection(mode, scenario_ids=scenario_ids),
            )
            case_directory = output_directory / f"iteration-{iteration:04d}" / mode.value
            if case_directory.exists():
                raise ValueError(f"chaos case output already exists: {case_directory}")
            case_directory.mkdir(parents=True)
            execution = execute_suite_resilient(
                gallery_directory=gallery_directory,
                output_directory=case_directory,
                adapter=adapter,
                run_prefix=f"chaos-{iteration:04d}-{mode.value}",
                max_workers=max_workers,
            )
            cases.append(ChaosCaseResult(iteration, mode, execution))
    return ChaosMatrixResult(tuple(cases), iterations, modes)
