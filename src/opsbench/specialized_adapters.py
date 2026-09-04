"""Reliability replay and cold-route scenario adapters for deterministic incident simulation."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import time
from typing import Any, Sequence

from opsbench.responses import BenchmarkResponse
from opsbench.scenarios import ScenarioPack


@dataclass(frozen=True)
class ReplayStep:
    """Recorded observation or action step in a multi-step incident timeline."""

    step_number: int
    elapsed_seconds: float
    event_type: str
    summary: str
    artifact_id: str | None = None
    action_taken: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.step_number, int) or self.step_number < 1:
            raise ValueError("step_number must be a positive integer")
        if not isinstance(self.elapsed_seconds, (int, float)) or self.elapsed_seconds < 0:
            raise ValueError("elapsed_seconds must be a non-negative float")
        if not isinstance(self.event_type, str) or not self.event_type.strip():
            raise ValueError("event_type must be a non-empty string")
        if not isinstance(self.summary, str) or not self.summary.strip():
            raise ValueError("summary must be a non-empty string")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "step_number": self.step_number,
            "elapsed_seconds": self.elapsed_seconds,
            "event_type": self.event_type,
            "summary": self.summary,
        }
        if self.artifact_id is not None:
            result["artifact_id"] = self.artifact_id
        if self.action_taken is not None:
            result["action_taken"] = self.action_taken
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReplayStep:
        return cls(
            step_number=int(data["step_number"]),
            elapsed_seconds=float(data["elapsed_seconds"]),
            event_type=str(data["event_type"]),
            summary=str(data["summary"]),
            artifact_id=data.get("artifact_id"),
            action_taken=data.get("action_taken"),
        )


@dataclass(frozen=True)
class ReliabilityReplayTimeline:
    """Complete temporal replay trace recorded from an incident."""

    scenario_id: str
    initial_symptoms: str
    root_cause_analysis: str
    steps: tuple[ReplayStep, ...]
    resolution_actions: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.scenario_id, str) or not self.scenario_id.strip():
            raise ValueError("scenario_id must be a non-empty string")
        if not isinstance(self.initial_symptoms, str) or not self.initial_symptoms.strip():
            raise ValueError("initial_symptoms must be a non-empty string")
        if not isinstance(self.root_cause_analysis, str) or not self.root_cause_analysis.strip():
            raise ValueError("root_cause_analysis must be a non-empty string")
        if not isinstance(self.steps, tuple) or not self.steps:
            raise ValueError("steps must be a non-empty tuple of ReplayStep")
        if not isinstance(self.resolution_actions, tuple):
            raise ValueError("resolution_actions must be a tuple of strings")

    def to_dict(self) -> dict[str, Any]:
        return {
            "initial_symptoms": self.initial_symptoms,
            "resolution_actions": list(self.resolution_actions),
            "root_cause_analysis": self.root_cause_analysis,
            "scenario_id": self.scenario_id,
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReliabilityReplayTimeline:
        steps = tuple(ReplayStep.from_dict(s) for s in data["steps"])
        return cls(
            scenario_id=str(data["scenario_id"]),
            initial_symptoms=str(data["initial_symptoms"]),
            root_cause_analysis=str(data["root_cause_analysis"]),
            steps=steps,
            resolution_actions=tuple(str(a) for a in data.get("resolution_actions", ())),
        )


class ReliabilityReplayAdapter:
    """Adapter that replays historical incident execution sequences and generates evidence-grounded responses."""

    def __init__(
        self,
        timeline: ReliabilityReplayTimeline,
        *,
        playback_speed: float = 1.0,
        adapter_name: str = "reliability-replay",
    ) -> None:
        if not isinstance(timeline, ReliabilityReplayTimeline):
            raise ValueError("timeline must be a ReliabilityReplayTimeline")
        if not isinstance(playback_speed, (int, float)) or playback_speed <= 0:
            raise ValueError("playback_speed must be a positive number")
        if not isinstance(adapter_name, str) or not adapter_name.strip():
            raise ValueError("adapter_name must be a non-empty string")

        self._timeline = timeline
        self._playback_speed = float(playback_speed)
        self._name = adapter_name.strip()

    @property
    def adapter_name(self) -> str:
        return self._name

    @property
    def timeline(self) -> ReliabilityReplayTimeline:
        return self._timeline

    def respond(self, pack: ScenarioPack) -> BenchmarkResponse:
        """Replay the incident timeline against the scenario pack and produce a structured response."""
        if not isinstance(pack, ScenarioPack):
            raise ValueError("pack must be a ScenarioPack")
        if pack.manifest.scenario_id != self._timeline.scenario_id:
            raise ValueError(
                f"replay timeline scenario_id {self._timeline.scenario_id!r} does not match pack {pack.manifest.scenario_id!r}"
            )

        # Collect cited artifacts from steps matching evidence in scenario
        available_artifact_ids = {art.artifact_id for art in pack.evidence}
        cited_artifacts: list[str] = []
        for step in self._timeline.steps:
            if step.artifact_id and step.artifact_id in available_artifact_ids:
                if step.artifact_id not in cited_artifacts:
                    cited_artifacts.append(step.artifact_id)

        # Build analysis synthesizing initial symptoms and steps
        step_narrative = " -> ".join(
            f"Step {s.step_number} ({s.event_type}): {s.summary}" for s in self._timeline.steps
        )
        full_analysis = f"{self._timeline.root_cause_analysis} Replay verification: {step_narrative}."

        return BenchmarkResponse(
            scenario_id=pack.manifest.scenario_id,
            analysis=full_analysis,
            cited_artifact_ids=tuple(cited_artifacts),
            proposed_actions=self._timeline.resolution_actions,
            model_name="reliability-replay-engine",
            adapter_name=self.adapter_name,
        )


@dataclass(frozen=True)
class ColdRouteProfile:
    """Operational profile of a dormant or rarely-used disaster recovery / failover route."""

    route_id: str
    target_environment: str
    last_verified_timestamp: str | None
    warmup_duration_seconds: float
    fallback_actions: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.route_id, str) or not self.route_id.strip():
            raise ValueError("route_id must be a non-empty string")
        if not isinstance(self.target_environment, str) or not self.target_environment.strip():
            raise ValueError("target_environment must be a non-empty string")
        if not isinstance(self.warmup_duration_seconds, (int, float)) or self.warmup_duration_seconds < 0:
            raise ValueError("warmup_duration_seconds must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "fallback_actions": list(self.fallback_actions),
            "route_id": self.route_id,
            "target_environment": self.target_environment,
            "warmup_duration_seconds": self.warmup_duration_seconds,
        }
        if self.last_verified_timestamp is not None:
            result["last_verified_timestamp"] = self.last_verified_timestamp
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ColdRouteProfile:
        return cls(
            route_id=str(data["route_id"]),
            target_environment=str(data["target_environment"]),
            last_verified_timestamp=data.get("last_verified_timestamp"),
            warmup_duration_seconds=float(data.get("warmup_duration_seconds", 0.0)),
            fallback_actions=tuple(str(a) for a in data.get("fallback_actions", ())),
        )


def load_replay_timeline(path: Path | str) -> ReliabilityReplayTimeline:
    """Load a reliability replay timeline from a JSON file."""
    p = Path(path)
    if not p.is_file():
        raise ValueError(f"replay timeline file not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("replay timeline root must be a JSON object")
    return ReliabilityReplayTimeline.from_dict(data)


def write_replay_timeline(path: Path | str, timeline: ReliabilityReplayTimeline) -> None:
    """Serialize and write a reliability replay timeline to a JSON file."""
    if not isinstance(timeline, ReliabilityReplayTimeline):
        raise ValueError("timeline must be a ReliabilityReplayTimeline")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(timeline.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_cold_routes(path: Path | str) -> tuple[ColdRouteProfile, ...]:
    """Load a collection of cold route profiles from a JSON file."""
    p = Path(path)
    if not p.is_file():
        raise ValueError(f"cold routes file not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("cold routes file must contain a JSON array of route objects")
    return tuple(ColdRouteProfile.from_dict(d) for d in data)


def write_cold_routes(path: Path | str, routes: Sequence[ColdRouteProfile]) -> None:
    """Serialize and write cold route profiles to a JSON file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    serialized = [r.to_dict() for r in routes]
    p.write_text(json.dumps(serialized, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class ColdRouteAdapter:
    """Specialized adapter simulating cold-route failover, disaster recovery routing, and un-warmed paths."""

    def __init__(
        self,
        cold_routes: Sequence[ColdRouteProfile],
        fallback_response_provider: callable,
        *,
        adapter_name: str = "cold-route",
    ) -> None:
        if not cold_routes:
            raise ValueError("cold_routes must not be empty")
        for route in cold_routes:
            if not isinstance(route, ColdRouteProfile):
                raise ValueError("each route must be a ColdRouteProfile")
        if not callable(fallback_response_provider):
            raise ValueError("fallback_response_provider must be callable")
        if not isinstance(adapter_name, str) or not adapter_name.strip():
            raise ValueError("adapter_name must be a non-empty string")

        self._cold_routes = {route.route_id: route for route in cold_routes}
        self._provider = fallback_response_provider
        self._name = adapter_name.strip()

    @property
    def adapter_name(self) -> str:
        return self._name

    @property
    def cold_routes(self) -> dict[str, ColdRouteProfile]:
        return dict(self._cold_routes)

    def route_for_scenario(self, scenario_id: str) -> ColdRouteProfile | None:
        """Find matching cold route if scenario specifies or maps to one."""
        for route_id, route in self._cold_routes.items():
            if route_id in scenario_id:
                return route
        return None

    def respond(self, pack: ScenarioPack) -> BenchmarkResponse:
        """Produce response taking into account cold-route failover actions and latency."""
        if not isinstance(pack, ScenarioPack):
            raise ValueError("pack must be a ScenarioPack")

        matching_route = self.route_for_scenario(pack.manifest.scenario_id)
        base_response: BenchmarkResponse = self._provider(pack)

        if matching_route is not None:
            # Augment actions with cold-route failover procedure
            augmented_actions = list(base_response.proposed_actions)
            for action in matching_route.fallback_actions:
                if action not in augmented_actions:
                    augmented_actions.append(action)

            augmented_analysis = (
                f"{base_response.analysis} [ColdRoute Activated: route '{matching_route.route_id}' "
                f"targeting '{matching_route.target_environment}' with warmup delay "
                f"{matching_route.warmup_duration_seconds:.1f}s]"
            )
            return BenchmarkResponse(
                scenario_id=pack.manifest.scenario_id,
                analysis=augmented_analysis,
                cited_artifact_ids=base_response.cited_artifact_ids,
                proposed_actions=tuple(augmented_actions),
                model_name=base_response.model_name or "cold-route-model",
                adapter_name=self.adapter_name,
            )

        return BenchmarkResponse(
            scenario_id=base_response.scenario_id,
            analysis=base_response.analysis,
            cited_artifact_ids=base_response.cited_artifact_ids,
            proposed_actions=base_response.proposed_actions,
            model_name=base_response.model_name,
            adapter_name=self.adapter_name,
        )
