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