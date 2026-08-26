"""Deterministic summaries for comparing immutable benchmark result bundles."""

from __future__ import annotations

from dataclasses import dataclass

from opsbench.runs import ResultBundle


@dataclass(frozen=True)
class ComparisonSummary:
    """Aggregate result totals for a single scenario and its runners."""

    scenario_id: str
    runner_totals: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.scenario_id, str) or not self.scenario_id.strip():
            raise ValueError("scenario_id must be a non-empty string")
        if not isinstance(self.runner_totals, tuple) or not all(
            isinstance(name, str) and name.strip() and isinstance(total, int)
            for name, total in self.runner_totals
        ):
            raise ValueError("runner_totals must contain non-empty names and integer totals")


@dataclass(frozen=True)
class RunnerStatistics:
    """Repeated-trial score statistics for one runner on one scenario."""

    runner_name: str
    trial_count: int
    total_score: int

    def __post_init__(self) -> None:
        if not isinstance(self.runner_name, str) or not self.runner_name.strip():
            raise ValueError("runner_name must be a non-empty string")
        if not isinstance(self.trial_count, int) or self.trial_count <= 0:
            raise ValueError("trial_count must be a positive integer")
        if not isinstance(self.total_score, int):
            raise ValueError("total_score must be an integer")

    @property
    def average_score(self) -> float:
        return self.total_score / self.trial_count


def compare_bundles(bundles: tuple[ResultBundle, ...]) -> ComparisonSummary:
    """Summarize same-scenario bundles by runner identity in stable order."""
    if not isinstance(bundles, tuple) or not bundles:
        raise ValueError("bundles must be a non-empty tuple of ResultBundle values")
    if not all(isinstance(bundle, ResultBundle) for bundle in bundles):
        raise ValueError("bundles must be a non-empty tuple of ResultBundle values")

    scenario_ids = {bundle.report.scenario_id for bundle in bundles}
    if len(scenario_ids) != 1:
        raise ValueError("all bundles must belong to the same scenario")

    totals: dict[str, int] = {}
    for bundle in bundles:
        runner_name = bundle.run.model_name or bundle.run.runner_kind
        totals[runner_name] = totals.get(runner_name, 0) + bundle.report.total
    return ComparisonSummary(
        scenario_id=next(iter(scenario_ids)),
        runner_totals=tuple(sorted(totals.items())),
    )


def summarize_trials(bundles: tuple[ResultBundle, ...]) -> tuple[RunnerStatistics, ...]:
    """Return stable per-runner trial counts and average-ready totals."""
    comparison = compare_bundles(bundles)
    trial_counts: dict[str, int] = {}
    for bundle in bundles:
        runner_name = bundle.run.model_name or bundle.run.runner_kind
        trial_counts[runner_name] = trial_counts.get(runner_name, 0) + 1
    return tuple(
        RunnerStatistics(
            runner_name=runner_name,
            trial_count=trial_counts[runner_name],
            total_score=total_score,
        )
        for runner_name, total_score in comparison.runner_totals
    )