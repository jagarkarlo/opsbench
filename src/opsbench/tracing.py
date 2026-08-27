"""OpenTelemetry-compatible span and trace context primitives for OpsBench."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
import uuid


@dataclass(frozen=True)
class TraceSpan:
    """Immutable trace span record representing an execution phase."""

    name: str
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    started_at: str = ""
    attributes: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string")
        if not isinstance(self.trace_id, str) or not self.trace_id.strip():
            raise ValueError("trace_id must be a non-empty string")
        if not isinstance(self.span_id, str) or not self.span_id.strip():
            raise ValueError("span_id must be a non-empty string")

        if not self.started_at:
            object.__setattr__(self, "started_at", datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, str | None | dict[str, str]]:
        return {
            "attributes": dict(self.attributes),
            "name": self.name,
            "parent_span_id": self.parent_span_id,
            "span_id": self.span_id,
            "started_at": self.started_at,
            "trace_id": self.trace_id,
        }


class TraceTracer:
    """Lightweight tracer for recording OpenTelemetry trace spans without external dependencies."""

    def __init__(self, service_name: str = "opsbench-service") -> None:
        self.service_name = service_name
        self._spans: list[TraceSpan] = []

    def start_span(
        self,
        name: str,
        *,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        attributes: dict[str, str] | None = None,
    ) -> TraceSpan:
        t_id = trace_id or uuid.uuid4().hex
        s_id = uuid.uuid4().hex[0:16]
        attrs = tuple(sorted((attributes or {}).items()))
        span = TraceSpan(
            name=name,
            trace_id=t_id,
            span_id=s_id,
            parent_span_id=parent_span_id,
            attributes=attrs,
        )
        self._spans.append(span)
        return span

    def recorded_spans(self) -> tuple[TraceSpan, ...]:
        return tuple(self._spans)

    def clear(self) -> None:
        self._spans.clear()
