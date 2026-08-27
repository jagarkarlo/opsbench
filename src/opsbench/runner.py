"""Local deterministic benchmark execution orchestration."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from opsbench.adapters import ResponseAdapter
from opsbench.runs import BenchmarkRun, ResultBundle, write_result_bundle
from opsbench.scenarios import ScenarioPack, load_scenario_pack
from opsbench.scoring import EvaluatorProfile, ScoreReport, evaluate_response, load_evaluator_profile


@dataclass(frozen=True)
class RunResult:
    """The immutable run request and its deterministic evaluator output."""

    run: BenchmarkRun
    report: ScoreReport


def execute_run(
    *,
    run_id: str,
    pack: ScenarioPack,
    profile: EvaluatorProfile,
    adapter: ResponseAdapter,
    started_at: datetime | None = None,
    metadata: tuple[tuple[str, str], ...] = (),
) -> RunResult:
    """Execute one local response adapter and evaluate it without side effects."""
    if not isinstance(pack, ScenarioPack):
        raise ValueError("pack must be a ScenarioPack")
    if not isinstance(profile, EvaluatorProfile):
        raise ValueError("profile must be an EvaluatorProfile")
    if profile.scenario_id != pack.manifest.scenario_id:
        raise ValueError("profile scenario_id must match the scenario pack")

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


def execute_suite(
    *,
    gallery_directory: Path,
    output_directory: Path,
    adapter: ResponseAdapter,
    run_prefix: str = "suite-run",
    started_at: datetime | None = None,
    metadata: tuple[tuple[str, str], ...] = (),
    max_workers: int = 1,
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
        )
        bundle = ResultBundle(run_result.run, run_result.report)
        write_result_bundle(output_directory / f"{run_id}.json", bundle)
        return bundle

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