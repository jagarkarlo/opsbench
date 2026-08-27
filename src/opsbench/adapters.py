"""Provider-neutral interfaces for producing benchmark responses."""

from __future__ import annotations

from typing import Protocol

from opsbench.responses import BenchmarkResponse
from opsbench.scenarios import ScenarioPack


class ResponseAdapter(Protocol):
    """Produces one normalized response for one fully loaded scenario pack."""

    @property
    def adapter_name(self) -> str:
        """Return a stable adapter identity recorded in benchmark runs."""

    def respond(self, pack: ScenarioPack) -> BenchmarkResponse:
        """Return a response without executing any proposed remediation action."""


class FixtureResponseAdapter:
    """Returns a fixed response for reproducible local benchmark runs."""

    def __init__(self, response: BenchmarkResponse, *, name: str = "fixture") -> None:
        if not isinstance(response, BenchmarkResponse):
            raise ValueError("response must be a BenchmarkResponse")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string")
        self._response = response
        self._name = name

    @property
    def adapter_name(self) -> str:
        return self._name

    def respond(self, pack: ScenarioPack) -> BenchmarkResponse:
        if not isinstance(pack, ScenarioPack):
            raise ValueError("pack must be a ScenarioPack")
        if self._response.scenario_id != pack.manifest.scenario_id:
            raise ValueError("fixture response scenario_id must match the scenario pack")
        return BenchmarkResponse(
            scenario_id=self._response.scenario_id,
            analysis=self._response.analysis,
            cited_artifact_ids=self._response.cited_artifact_ids,
            proposed_actions=self._response.proposed_actions,
            model_name=self._response.model_name,
            adapter_name=self.adapter_name,
        )


class HumanResponseAdapter(FixtureResponseAdapter):
    """Returns a locally supplied human response for a benchmark run."""

    def __init__(self, response: BenchmarkResponse) -> None:
        super().__init__(response, name="human")


class GalleryFixtureResponseAdapter:
    """Returns pre-loaded fixture responses matching scenario IDs across a gallery."""

    def __init__(
        self,
        responses: dict[str, BenchmarkResponse],
        *,
        name: str = "fixture",
    ) -> None:
        if not isinstance(responses, dict) or not responses:
            raise ValueError("responses must be a non-empty dictionary mapping scenario_id to BenchmarkResponse")
        for scenario_id, response in responses.items():
            if not isinstance(scenario_id, str) or not scenario_id.strip():
                raise ValueError("scenario_id key must be a non-empty string")
            if not isinstance(response, BenchmarkResponse):
                raise ValueError(f"response for {scenario_id} must be a BenchmarkResponse")
            if response.scenario_id != scenario_id:
                raise ValueError(
                    f"response scenario_id {response.scenario_id!r} does not match key {scenario_id!r}"
                )
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string")
        self._responses = dict(responses)
        self._name = name

    @property
    def adapter_name(self) -> str:
        return self._name

    def respond(self, pack: ScenarioPack) -> BenchmarkResponse:
        if not isinstance(pack, ScenarioPack):
            raise ValueError("pack must be a ScenarioPack")
        scenario_id = pack.manifest.scenario_id
        if scenario_id not in self._responses:
            raise ValueError(f"no fixture response available for scenario: {scenario_id}")
        response = self._responses[scenario_id]
        return BenchmarkResponse(
            scenario_id=response.scenario_id,
            analysis=response.analysis,
            cited_artifact_ids=response.cited_artifact_ids,
            proposed_actions=response.proposed_actions,
            model_name=response.model_name,
            adapter_name=self.adapter_name,
        )