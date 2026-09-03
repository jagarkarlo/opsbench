"""Deterministic synthetic failures for local benchmark evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from opsbench.adapters import ResponseAdapter
from opsbench.responses import BenchmarkResponse
from opsbench.scenarios import ScenarioPack


class FailureMode(str, Enum):
    """Synthetic failure modes that do not touch external infrastructure."""

    TIMEOUT = "timeout"
    MALFORMED_RESPONSE = "malformed_response"
    MISSING_EVIDENCE = "missing_evidence"
    ADAPTER_EXCEPTION = "adapter_exception"


class InjectedFailureError(RuntimeError):
    """Expected synthetic failure raised by a failure-injecting adapter."""

    def __init__(self, mode: FailureMode, scenario_id: str) -> None:
        self.mode = mode
        self.scenario_id = scenario_id
        super().__init__(f"injected {mode.value} for scenario {scenario_id}")

    def to_dict(self) -> dict[str, str]:
        """Return the stable structured representation for CLI reporting."""
        return {"mode": self.mode.value, "scenario_id": self.scenario_id}


class InjectedTimeoutError(TimeoutError, InjectedFailureError):
    """Expected synthetic timeout."""

    def __init__(self, mode: FailureMode, scenario_id: str) -> None:
        InjectedFailureError.__init__(self, mode, scenario_id)


class InjectedMalformedResponseError(ValueError, InjectedFailureError):
    """Expected synthetic malformed response."""

    def __init__(self, mode: FailureMode, scenario_id: str) -> None:
        InjectedFailureError.__init__(self, mode, scenario_id)


@dataclass(frozen=True)
class FailureInjection:
    """Immutable configuration for applying one synthetic failure to selected scenarios."""

    mode: FailureMode
    scenario_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.mode, FailureMode):
            raise ValueError("mode must be a FailureMode")
        if not isinstance(self.scenario_ids, tuple) or not all(
            isinstance(scenario_id, str) and scenario_id.strip()
            for scenario_id in self.scenario_ids
        ):
            raise ValueError("scenario_ids must be a tuple of non-empty strings")
        if len(set(self.scenario_ids)) != len(self.scenario_ids):
            raise ValueError("scenario_ids must be unique")

    def applies_to(self, scenario_id: str) -> bool:
        """Return whether this injection targets a scenario, or all scenarios when unset."""
        if not isinstance(scenario_id, str) or not scenario_id.strip():
            raise ValueError("scenario_id must be a non-empty string")
        return not self.scenario_ids or scenario_id in self.scenario_ids


class FailureInjectingAdapter:
    """Wrap a response adapter and apply one deterministic synthetic failure."""

    def __init__(self, adapter: ResponseAdapter, injection: FailureInjection) -> None:
        if not isinstance(injection, FailureInjection):
            raise ValueError("injection must be a FailureInjection")
        if not isinstance(getattr(adapter, "adapter_name", None), str):
            raise ValueError("adapter must provide an adapter_name")
        self._adapter = adapter
        self._injection = injection

    @property
    def adapter_name(self) -> str:
        return f"{self._adapter.adapter_name}+failure:{self._injection.mode.value}"

    def respond(self, pack: ScenarioPack) -> BenchmarkResponse:
        if not isinstance(pack, ScenarioPack):
            raise ValueError("pack must be a ScenarioPack")

        if not self._injection.applies_to(pack.manifest.scenario_id):
            return self._adapter.respond(pack)

        mode = self._injection.mode
        if mode is FailureMode.TIMEOUT:
            raise InjectedTimeoutError(mode, pack.manifest.scenario_id)
        if mode is FailureMode.MALFORMED_RESPONSE:
            raise InjectedMalformedResponseError(mode, pack.manifest.scenario_id)
        if mode is FailureMode.ADAPTER_EXCEPTION:
            raise InjectedFailureError(mode, pack.manifest.scenario_id)
        response = self._adapter.respond(pack)
        if mode is FailureMode.MISSING_EVIDENCE:
            return BenchmarkResponse(
                scenario_id=response.scenario_id,
                analysis=response.analysis,
                cited_artifact_ids=(*response.cited_artifact_ids, "injected-missing-evidence"),
                proposed_actions=response.proposed_actions,
                model_name=response.model_name,
                adapter_name=self.adapter_name,
            )
        raise ValueError(f"unsupported failure mode: {mode!r}")