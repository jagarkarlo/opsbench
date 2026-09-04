"""Deterministic summaries for comparing immutable benchmark result bundles."""

from __future__ import annotations

from dataclasses import dataclass
import math

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
    total_squared_score: int

    def __post_init__(self) -> None:
        if not isinstance(self.runner_name, str) or not self.runner_name.strip():
            raise ValueError("runner_name must be a non-empty string")
        if not isinstance(self.trial_count, int) or self.trial_count <= 0:
            raise ValueError("trial_count must be a positive integer")
        if not isinstance(self.total_score, int):
            raise ValueError("total_score must be an integer")
        if not isinstance(self.total_squared_score, int):
            raise ValueError("total_squared_score must be an integer")
        if self.total_squared_score < 0:
            raise ValueError("total_squared_score must not be negative")

    @property
    def average_score(self) -> float:
        return self.total_score / self.trial_count

    @property
    def variance(self) -> float:
        """Return the unbiased sample variance of trial scores."""
        if self.trial_count < 2:
            return 0.0
        numerator = self.total_squared_score - (self.total_score**2 / self.trial_count)
        return max(numerator / (self.trial_count - 1), 0.0)

    @property
    def standard_deviation(self) -> float:
        """Return the sample standard deviation of trial scores."""
        return math.sqrt(self.variance)

    @property
    def confidence_interval_95(self) -> tuple[float, float]:
        """Return a normal-approximation 95% confidence interval for the mean."""
        margin = 1.96 * self.standard_deviation / math.sqrt(self.trial_count)
        return self.average_score - margin, self.average_score + margin

    @property
    def conservative_score(self) -> float:
        """Return the lower 95% confidence bound used for ranking."""
        return self.confidence_interval_95[0]


@dataclass(frozen=True)
class PortfolioStatistics:
    """Normalized repeated-trial statistics across a scenario portfolio."""

    runner_name: str
    trial_count: int
    scenario_count: int
    total_normalized_score: float
    total_squared_normalized_score: float

    def __post_init__(self) -> None:
        if not isinstance(self.runner_name, str) or not self.runner_name.strip():
            raise ValueError("runner_name must be a non-empty string")
        if not isinstance(self.trial_count, int) or self.trial_count <= 0:
            raise ValueError("trial_count must be a positive integer")
        if not isinstance(self.scenario_count, int) or self.scenario_count <= 0:
            raise ValueError("scenario_count must be a positive integer")
        if self.scenario_count > self.trial_count:
            raise ValueError("scenario_count must not exceed trial_count")
        if self.total_normalized_score < 0:
            raise ValueError("total_normalized_score must not be negative")
        if self.total_squared_normalized_score < 0:
            raise ValueError("total_squared_normalized_score must not be negative")

    @property
    def average_score(self) -> float:
        return self.total_normalized_score / self.trial_count

    @property
    def variance(self) -> float:
        if self.trial_count < 2:
            return 0.0
        numerator = self.total_squared_normalized_score - (
            self.total_normalized_score**2 / self.trial_count
        )
        return max(numerator / (self.trial_count - 1), 0.0)

    @property
    def standard_deviation(self) -> float:
        return math.sqrt(self.variance)

    @property
    def confidence_interval_95(self) -> tuple[float, float]:
        margin = 1.96 * self.standard_deviation / math.sqrt(self.trial_count)
        return self.average_score - margin, self.average_score + margin

    @property
    def conservative_score(self) -> float:
        return self.confidence_interval_95[0]


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
    squared_totals: dict[str, int] = {}
    for bundle in bundles:
        runner_name = bundle.run.model_name or bundle.run.runner_kind
        trial_counts[runner_name] = trial_counts.get(runner_name, 0) + 1
        squared_totals[runner_name] = squared_totals.get(runner_name, 0) + bundle.report.total**2
    return tuple(
        RunnerStatistics(
            runner_name=runner_name,
            trial_count=trial_counts[runner_name],
            total_score=total_score,
            total_squared_score=squared_totals[runner_name],
        )
        for runner_name, total_score in comparison.runner_totals
    )


def rank_trials(bundles: tuple[ResultBundle, ...]) -> tuple[RunnerStatistics, ...]:
    """Rank runners by conservative score, then mean and sample size."""
    return tuple(
        sorted(
            summarize_trials(bundles),
            key=lambda statistic: (
                -statistic.conservative_score,
                -statistic.average_score,
                -statistic.trial_count,
                statistic.runner_name,
            ),
        )
    )


def summarize_portfolio(bundles: tuple[ResultBundle, ...]) -> tuple[PortfolioStatistics, ...]:
    """Summarize runner performance across multiple scenario IDs."""
    if not isinstance(bundles, tuple) or not bundles:
        raise ValueError("bundles must be a non-empty tuple of ResultBundle values")
    if not all(isinstance(bundle, ResultBundle) for bundle in bundles):
        raise ValueError("bundles must be a non-empty tuple of ResultBundle values")

    totals: dict[str, float] = {}
    squared_totals: dict[str, float] = {}
    trial_counts: dict[str, int] = {}
    scenarios: dict[str, set[str]] = {}
    for bundle in bundles:
        runner_name = bundle.run.model_name or bundle.run.runner_kind
        normalized_score = bundle.report.total / bundle.report.maximum
        totals[runner_name] = totals.get(runner_name, 0.0) + normalized_score
        squared_totals[runner_name] = squared_totals.get(runner_name, 0.0) + normalized_score**2
        trial_counts[runner_name] = trial_counts.get(runner_name, 0) + 1
        scenarios.setdefault(runner_name, set()).add(bundle.report.scenario_id)

    return tuple(
        PortfolioStatistics(
            runner_name=runner_name,
            trial_count=trial_counts[runner_name],
            scenario_count=len(scenarios[runner_name]),
            total_normalized_score=totals[runner_name],
            total_squared_normalized_score=squared_totals[runner_name],
        )
        for runner_name in sorted(totals)
    )


def rank_portfolio(bundles: tuple[ResultBundle, ...]) -> tuple[PortfolioStatistics, ...]:
    """Rank portfolio results by conservative normalized score and coverage."""
    return tuple(
        sorted(
            summarize_portfolio(bundles),
            key=lambda statistic: (
                -statistic.conservative_score,
                -statistic.average_score,
                -statistic.scenario_count,
                -statistic.trial_count,
                statistic.runner_name,
            ),
        )
    )


def render_markdown_comparison(bundles: tuple[ResultBundle, ...]) -> str:
    """Render a clean Markdown comparison report from result bundles."""
    summary = compare_bundles(bundles)
    trials = summarize_trials(bundles)
    lines = [
        "# OpsBench Comparison Report",
        "",
        f"**Scenario**: `{summary.scenario_id}`",
        "",
        "| Runner | Trials | Total Score | Average Score | Std. Dev. | 95% CI |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for statistic in trials:
        interval = statistic.confidence_interval_95
        lines.append(
            f"| {statistic.runner_name} | {statistic.trial_count} | {statistic.total_score} | "
            f"{statistic.average_score:.2f} | {statistic.standard_deviation:.2f} | "
            f"[{interval[0]:.2f}, {interval[1]:.2f}] |"
        )
    return "\n".join(lines) + "\n"


def render_markdown_leaderboard(bundles: tuple[ResultBundle, ...]) -> str:
    """Render a ranked leaderboard with uncertainty-aware scores."""
    summary = compare_bundles(bundles)
    lines = [
        "# OpsBench Leaderboard",
        "",
        f"**Scenario**: `{summary.scenario_id}`",
        "",
        "| Rank | Runner | Trials | Average Score | Conservative Score | 95% CI |",
        "|---:|---|---:|---:|---:|---|",
    ]
    for rank, statistic in enumerate(rank_trials(bundles), start=1):
        interval = statistic.confidence_interval_95
        lines.append(
            f"| {rank} | {statistic.runner_name} | {statistic.trial_count} | "
            f"{statistic.average_score:.2f} | {statistic.conservative_score:.2f} | "
            f"[{interval[0]:.2f}, {interval[1]:.2f}] |"
        )
    return "\n".join(lines) + "\n"
