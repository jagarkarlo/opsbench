"""Local deterministic benchmark execution orchestration."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from opsbench.adapters import ResponseAdapter
from opsbench.failure_injection import InjectedFailureError
from opsbench.runs import BenchmarkRun, ResultBundle, write_result_bundle
from opsbench.scenarios import ScenarioPack, load_scenario_pack
from opsbench.scoring import EvaluatorProfile, ScoreReport, evaluate_response, load_evaluator_profile
from opsbench.tracing import TraceSpan, TraceTracer


@dataclass(frozen=True)
class RunResult:
    """The immutable run request and its deterministic evaluator output."""

    run: BenchmarkRun
    report: ScoreReport


@dataclass(frozen=True)
class SuiteFailure:
    """One expected injected failure captured while a suite continues."""

    run_id: str
    failure: InjectedFailureError

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ValueError("run_id must be a non-empty string")
        if not isinstance(self.failure, InjectedFailureError):
            raise ValueError("failure must be an InjectedFailureError")

    def to_dict(self) -> dict[str, str | dict[str, str]]:
        return {"failure": self.failure.to_dict(), "run_id": self.run_id}


@dataclass(frozen=True)
class SuiteExecution:
    """Completed suite bundles and expected injected failures in gallery order."""

    bundles: tuple[ResultBundle, ...]
    failures: tuple[SuiteFailure, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.bundles, tuple) or not all(
            isinstance(bundle, ResultBundle) for bundle in self.bundles
        ):
            raise ValueError("bundles must be a tuple of ResultBundle values")
        if not isinstance(self.failures, tuple) or not all(
            isinstance(failure, SuiteFailure) for failure in self.failures
        ):
            raise ValueError("failures must be a tuple of SuiteFailure values")

    @property
    def scenario_count(self) -> int:
        """Return the number of completed and expected-failure scenarios."""
        return len(self.bundles) + len(self.failures)


def execute_run(
    *,
    run_id: str,
    pack: ScenarioPack,
    profile: EvaluatorProfile,
    adapter: ResponseAdapter,
    started_at: datetime | None = None,
    metadata: tuple[tuple[str, str], ...] = (),
    tracer: TraceTracer | None = None,
    parent_span: TraceSpan | None = None,
) -> RunResult:
    """Execute one local response adapter and evaluate it without side effects."""
    if not isinstance(pack, ScenarioPack):
        raise ValueError("pack must be a ScenarioPack")
    if not isinstance(profile, EvaluatorProfile):
        raise ValueError("profile must be an EvaluatorProfile")
    if profile.scenario_id != pack.manifest.scenario_id:
        raise ValueError("profile scenario_id must match the scenario pack")

    run_span = (
        tracer.start_span(
            "execute_run",
            trace_id=parent_span.trace_id if parent_span else None,
            parent_span_id=parent_span.span_id if parent_span else None,
            attributes={"run_id": run_id, "scenario_id": pack.manifest.scenario_id},
        )
        if tracer is not None
        else None
    )

    try:
        response = adapter.respond(pack)
        timestamp = started_at or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            raise ValueError("started_at must include a timezone")
        run = BenchmarkRun(
            run_id=run_id,
            runner_kind=adapter.adapter_name,
            started_at=timestamp.isoformat(),
            scenario_pack_hash=pack.content_hash(),
            evaluator_profile_hash=profile.content_hash(),
            response_hash=response.content_hash(),
            model_name=response.model_name,
            metadata=metadata,
        )
        report = evaluate_response(pack, profile, response)
        return RunResult(run=run, report=report)
    finally:
        if tracer is not None and run_span is not None:
            tracer.end_span(run_span)


def execute_suite(
    *,
    gallery_directory: Path,
    output_directory: Path,
    adapter: ResponseAdapter,
    run_prefix: str = "suite-run",
    started_at: datetime | None = None,
    metadata: tuple[tuple[str, str], ...] = (),
    max_workers: int = 1,
    tracer: TraceTracer | None = None,
) -> tuple[ResultBundle, ...]:
    """Execute a response adapter across an entire scenario gallery and write immutable result bundles."""
    if not isinstance(gallery_directory, Path) or not gallery_directory.is_dir():
        raise ValueError(f"gallery_directory must be a directory: {gallery_directory}")
    if not isinstance(output_directory, Path):
        raise ValueError("output_directory must be a Path")
    if not isinstance(run_prefix, str) or not run_prefix.strip():
        raise ValueError("run_prefix must be a non-empty string")
    if not isinstance(max_workers, int) or max_workers <= 0:
        raise ValueError("max_workers must be a positive integer")

    scenarios_to_run: list[tuple[Path, Path]] = []
    for candidate in sorted(gallery_directory.iterdir(), key=lambda path: path.name):
        if candidate.is_dir() and (candidate / "scenario.json").is_file():
            profile_path = candidate / "evaluator.json"
            if not profile_path.is_file():
                raise ValueError(f"scenario missing evaluator profile: {candidate}")
            scenarios_to_run.append((candidate, profile_path))

    if not scenarios_to_run:
        raise ValueError(f"no scenario packs found in gallery directory: {gallery_directory}")

    suite_span = (
        tracer.start_span("execute_suite", attributes={"run_prefix": run_prefix})
        if tracer is not None
        else None
    )

    def _run_single(dir_path: Path, profile_path: Path) -> ResultBundle:
        pack = load_scenario_pack(dir_path)
        profile = load_evaluator_profile(profile_path)
        run_id = f"{run_prefix}-{pack.manifest.scenario_id}"
        run_result = execute_run(
            run_id=run_id,
            pack=pack,
            profile=profile,
            adapter=adapter,
            started_at=started_at,
            metadata=metadata,
            tracer=tracer,
            parent_span=suite_span,
        )
        bundle = ResultBundle(run_result.run, run_result.report)
        write_result_bundle(output_directory / f"{run_id}.json", bundle)
        return bundle

    try:
        if max_workers == 1:
            bundles = [_run_single(dir_path, profile_path) for dir_path, profile_path in scenarios_to_run]
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [
                    executor.submit(_run_single, dir_path, profile_path)
                    for dir_path, profile_path in scenarios_to_run
                ]
                bundles = [future.result() for future in futures]

        return tuple(bundles)
    finally:
        if tracer is not None and suite_span is not None:
            tracer.end_span(suite_span)


def execute_suite_resilient(
    *,
    gallery_directory: Path,
    output_directory: Path,
    adapter: ResponseAdapter,
    run_prefix: str = "suite-run",
    started_at: datetime | None = None,
    metadata: tuple[tuple[str, str], ...] = (),
    max_workers: int = 1,
    tracer: TraceTracer | None = None,
) -> SuiteExecution:
    """Execute a suite while recording expected injected failures and continuing."""
    if not isinstance(gallery_directory, Path) or not gallery_directory.is_dir():
        raise ValueError(f"gallery_directory must be a directory: {gallery_directory}")
    if not isinstance(output_directory, Path):
        raise ValueError("output_directory must be a Path")
    if not isinstance(run_prefix, str) or not run_prefix.strip():
        raise ValueError("run_prefix must be a non-empty string")
    if not isinstance(max_workers, int) or max_workers <= 0:
        raise ValueError("max_workers must be a positive integer")

    scenarios_to_run: list[tuple[Path, Path]] = []
    for candidate in sorted(gallery_directory.iterdir(), key=lambda path: path.name):
        if candidate.is_dir() and (candidate / "scenario.json").is_file():
            profile_path = candidate / "evaluator.json"
            if not profile_path.is_file():
                raise ValueError(f"scenario missing evaluator profile: {candidate}")
            scenarios_to_run.append((candidate, profile_path))
    if not scenarios_to_run:
        raise ValueError(f"no scenario packs found in gallery directory: {gallery_directory}")

    suite_span = (
        tracer.start_span("execute_suite_resilient", attributes={"run_prefix": run_prefix})
        if tracer is not None
        else None
    )

    def _run_single(dir_path: Path, profile_path: Path) -> ResultBundle | SuiteFailure:
        pack = load_scenario_pack(dir_path)
        profile = load_evaluator_profile(profile_path)
        run_id = f"{run_prefix}-{pack.manifest.scenario_id}"
        try:
            run_result = execute_run(
                run_id=run_id,
                pack=pack,
                profile=profile,
                adapter=adapter,
                started_at=started_at,
                metadata=metadata,
                tracer=tracer,
                parent_span=suite_span,
            )
        except InjectedFailureError as error:
            return SuiteFailure(run_id, error)
        bundle = ResultBundle(run_result.run, run_result.report)
        write_result_bundle(output_directory / f"{run_id}.json", bundle)
        return bundle

    try:
        if max_workers == 1:
            outcomes = [_run_single(dir_path, profile_path) for dir_path, profile_path in scenarios_to_run]
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [
                    executor.submit(_run_single, dir_path, profile_path)
                    for dir_path, profile_path in scenarios_to_run
                ]
                outcomes = [future.result() for future in futures]
        return SuiteExecution(
            tuple(outcome for outcome in outcomes if isinstance(outcome, ResultBundle)),
            tuple(outcome for outcome in outcomes if isinstance(outcome, SuiteFailure)),
        )
    finally:
        if tracer is not None and suite_span is not None:
            tracer.end_span(suite_span)