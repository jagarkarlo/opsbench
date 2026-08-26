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