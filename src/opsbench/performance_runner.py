"""Profiled benchmark execution with performance metrics collection."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from opsbench.adapters import ResponseAdapter
from opsbench.performance import PerformanceMetrics, PerformanceProfiler
from opsbench.failure_injection import InjectedFailureError
from opsbench.runner import RunResult, SuiteFailure, execute_run
from opsbench.runs import ResultBundle
from opsbench.scenarios import ScenarioPack, load_scenario_pack
from opsbench.scoring import EvaluatorProfile, load_evaluator_profile
from opsbench.tracing import TraceSpan, TraceTracer


class ProfiledRunExecution:
    """Execution of a scenario run with associated performance metrics."""

    def __init__(self, run_result: RunResult, metrics: PerformanceMetrics) -> None:
        self._run_result = run_result
        self._metrics = metrics

    @property
    def run_result(self) -> RunResult:
        return self._run_result

    @property
    def metrics(self) -> PerformanceMetrics:
        return self._metrics


class ProfiledSuiteExecution:
    """Execution of a scenario suite with per-run and aggregate performance metrics."""

    def __init__(
        self,
        bundles: tuple[ResultBundle, ...],
        metrics: list[PerformanceMetrics],
        failures: tuple[SuiteFailure, ...] = (),
    ) -> None:
        self._bundles = bundles
        self._metrics = metrics
        self._failures = failures

    @property
    def bundles(self) -> tuple[ResultBundle, ...]:
        return self._bundles

    @property
    def individual_metrics(self) -> list[PerformanceMetrics]:
        return self._metrics

    @property
    def failures(self) -> tuple[SuiteFailure, ...]:
        return self._failures

    @property
    def scenario_count(self) -> int:
        return len(self._bundles) + len(self._failures)

    def aggregate_metrics(self) -> PerformanceMetrics:
        """Aggregate metrics across all runs in the suite."""
        if not self._metrics:
            raise ValueError("no metrics recorded")

        total_time = sum(m.wall_time_seconds for m in self._metrics)
        total_items = sum(m.items_processed for m in self._metrics)

        return PerformanceMetrics(
            name="suite-aggregate",
            wall_time_seconds=total_time,
            items_processed=total_items,
        )


def execute_run_profiled(
    *,
    run_id: str,
    pack: ScenarioPack,
    profile: EvaluatorProfile,
    adapter: ResponseAdapter,
    started_at: datetime | None = None,
    metadata: tuple[tuple[str, str], ...] = (),
    tracer: TraceTracer | None = None,
    parent_span: TraceSpan | None = None,
) -> ProfiledRunExecution:
    """Execute one scenario run with performance profiling."""
    profiler = PerformanceProfiler()

    def _execute() -> RunResult:
        return execute_run(
            run_id=run_id,
            pack=pack,
            profile=profile,
            adapter=adapter,
            started_at=started_at,
            metadata=metadata,
            tracer=tracer,
            parent_span=parent_span,
        )

    run_result = profiler.measure(
        name=f"run-{pack.manifest.scenario_id}",
        func=_execute,
        items_processed=1,
    )

    metrics = profiler.recorded_metrics()[0]
    return ProfiledRunExecution(run_result, metrics)


def execute_suite_profiled(
    *,
    gallery_directory: Path,
    output_directory: Path,
    adapter: ResponseAdapter,
    run_prefix: str = "suite-run",
    started_at: datetime | None = None,
    metadata: tuple[tuple[str, str], ...] = (),
    max_workers: int = 1,
    tracer: TraceTracer | None = None,
    resilient: bool = False,
) -> ProfiledSuiteExecution:
    """Execute a scenario suite with per-run profiling and optional failure capture."""
    if not isinstance(gallery_directory, Path) or not gallery_directory.is_dir():
        raise ValueError(f"gallery_directory must be a directory: {gallery_directory}")

    # Discover scenarios
    scenarios_to_run: list[tuple[Path, Path]] = []
    for candidate in sorted(gallery_directory.iterdir(), key=lambda path: path.name):
        if candidate.is_dir() and (candidate / "scenario.json").is_file():
            profile_path = candidate / "evaluator.json"
            if not profile_path.is_file():
                raise ValueError(f"scenario missing evaluator profile: {candidate}")
            scenarios_to_run.append((candidate, profile_path))

    if not scenarios_to_run:
        raise ValueError(f"no scenario packs found in gallery directory: {gallery_directory}")

    metrics: list[PerformanceMetrics] = []

    # Execute suite and record individual run metrics
    def _run_and_measure(
        dir_path: Path, profile_path: Path
    ) -> tuple[ResultBundle | SuiteFailure, PerformanceMetrics | None]:
        pack = load_scenario_pack(dir_path)
        profile = load_evaluator_profile(profile_path)
        run_id = f"{run_prefix}-{pack.manifest.scenario_id}"

        def _execute_single() -> RunResult:
            return execute_run(
                run_id=run_id,
                pack=pack,
                profile=profile,
                adapter=adapter,
                started_at=started_at,
                metadata=metadata,
                tracer=tracer,
            )

        profiler = PerformanceProfiler()
        try:
            run_result = profiler.measure(
                name=f"run-{pack.manifest.scenario_id}",
                func=_execute_single,
                items_processed=1,
            )
        except InjectedFailureError as error:
            if not resilient:
                raise
            return SuiteFailure(run_id, error), None
        recorded_metrics = profiler.recorded_metrics()[0]
        return ResultBundle(run_result.run, run_result.report), recorded_metrics

    from opsbench.runs import write_result_bundle

    bundles: list[ResultBundle] = []
    failures: list[SuiteFailure] = []
    if max_workers == 1:
        for dir_path, profile_path in scenarios_to_run:
            outcome, metric = _run_and_measure(dir_path, profile_path)
            if isinstance(outcome, SuiteFailure):
                failures.append(outcome)
            else:
                metrics.append(metric)
                bundles.append(outcome)
                write_result_bundle(output_directory / f"{outcome.run.run_id}.json", outcome)
    else:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(_run_and_measure, dir_path, profile_path)
                for dir_path, profile_path in scenarios_to_run
            ]
            for future in futures:
                outcome, metric = future.result()
                if isinstance(outcome, SuiteFailure):
                    failures.append(outcome)
                else:
                    metrics.append(metric)
                    bundles.append(outcome)
                    write_result_bundle(output_directory / f"{outcome.run.run_id}.json", outcome)

    return ProfiledSuiteExecution(tuple(bundles), metrics, tuple(failures))
