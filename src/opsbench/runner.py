"""Local deterministic benchmark execution orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from opsbench.adapters import ResponseAdapter
from opsbench.runs import BenchmarkRun
from opsbench.scenarios import ScenarioPack
from opsbench.scoring import EvaluatorProfile, ScoreReport, evaluate_response


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