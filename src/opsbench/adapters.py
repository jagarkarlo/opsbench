"""Provider-neutral interfaces for producing benchmark responses."""

from __future__ import annotations

import json
from typing import Protocol
import urllib.error
import urllib.request

from opsbench.prompts import render_prompt
from opsbench.responses import BenchmarkResponse, parse_response_text
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


class OpenAIResponseAdapter:
    """Produces benchmark responses from any OpenAI-compatible HTTP endpoint."""

    def __init__(
        self,
        *,
        model_name: str,
        api_base: str = "http://localhost:11434/v1",
        api_key: str | None = None,
        temperature: float = 0.0,
        timeout: float = 60.0,
        adapter_name: str = "openai-compatible",
    ) -> None:
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("model_name must be a non-empty string")
        if not isinstance(api_base, str) or not api_base.strip():
            raise ValueError("api_base must be a non-empty string")
        if not isinstance(adapter_name, str) or not adapter_name.strip():
            raise ValueError("adapter_name must be a non-empty string")
        if not isinstance(temperature, (int, float)) or temperature < 0:
            raise ValueError("temperature must be a non-negative number")
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ValueError("timeout must be a positive number")

        self._model_name = model_name.strip()
        self._api_base = api_base.rstrip("/")
        self._api_key = api_key.strip() if isinstance(api_key, str) and api_key.strip() else None
        self._temperature = float(temperature)
        self._timeout = float(timeout)
        self._name = adapter_name.strip()

    @property
    def adapter_name(self) -> str:
        return self._name

    def respond(self, pack: ScenarioPack) -> BenchmarkResponse:
        if not isinstance(pack, ScenarioPack):
            raise ValueError("pack must be a ScenarioPack")

        prompt_text = render_prompt(pack)
        payload = {
            "model": self._model_name,
            "messages": [
                {"role": "user", "content": prompt_text},
            ],
            "temperature": self._temperature,
        }
        data = json.dumps(payload).encode("utf-8")
        url = f"{self._api_base}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as error:
            raise RuntimeError(
                f"OpenAI endpoint call failed for scenario {pack.manifest.scenario_id}: {error}"
            ) from error

        try:
            content_text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError(
                f"malformed OpenAI API response payload for scenario {pack.manifest.scenario_id}"
            ) from error

        parsed_response = parse_response_text(content_text)
        if parsed_response.scenario_id != pack.manifest.scenario_id:
            raise ValueError(
                f"OpenAI model returned scenario_id {parsed_response.scenario_id!r}, expected {pack.manifest.scenario_id!r}"
            )

        return BenchmarkResponse(
            scenario_id=parsed_response.scenario_id,
            analysis=parsed_response.analysis,
            cited_artifact_ids=parsed_response.cited_artifact_ids,
            proposed_actions=parsed_response.proposed_actions,
            model_name=self._model_name,
            adapter_name=self.adapter_name,
        )