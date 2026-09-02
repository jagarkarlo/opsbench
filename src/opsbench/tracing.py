"""OpenTelemetry-compatible span and trace context primitives for OpsBench."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from urllib.error import URLError
from urllib.request import Request, urlopen
import uuid


@dataclass(frozen=True)
class TraceSpan:
    """Immutable trace span record representing an execution phase."""

    name: str
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    started_at: str = ""
    ended_at: str | None = None
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
            "ended_at": self.ended_at,
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

    def end_span(self, span: TraceSpan) -> TraceSpan:
        """Record the completion time for a previously started span."""
        if span not in self._spans:
            raise ValueError("span was not started by this tracer")
        if span.ended_at is not None:
            return span

        completed = TraceSpan(
            name=span.name,
            trace_id=span.trace_id,
            span_id=span.span_id,
            parent_span_id=span.parent_span_id,
            started_at=span.started_at,
            ended_at=datetime.now(timezone.utc).isoformat(),
            attributes=span.attributes,
        )
        self._spans[self._spans.index(span)] = completed
        return completed

    def otlp_payload(self) -> dict[str, object]:
        """Return completed spans encoded as an OTLP/HTTP JSON trace payload."""
        spans = [span for span in self._spans if span.ended_at is not None]
        return {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {
                                "key": "service.name",
                                "value": {"stringValue": self.service_name},
                            }
                        ]
                    },
                    "scopeSpans": [
                        {
                            "scope": {"name": "opsbench"},
                            "spans": [self._otlp_span(span) for span in spans],
                        }
                    ],
                }
            ]
        }

    def export_otlp(self, endpoint: str, timeout: float = 10.0) -> None:
        """Synchronously export completed spans to an OTLP/HTTP endpoint."""
        if not isinstance(endpoint, str) or not endpoint.strip():
            raise ValueError("endpoint must be a non-empty string")
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ValueError("timeout must be positive")

        request = Request(
            endpoint,
            data=json.dumps(self.otlp_payload(), sort_keys=True).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout):
                pass
        except URLError as error:
            raise ValueError(f"unable to export OTLP traces: {error.reason}") from error

    @staticmethod
    def _otlp_span(span: TraceSpan) -> dict[str, object]:
        return {
            "attributes": [
                {"key": key, "value": {"stringValue": value}}
                for key, value in span.attributes
            ],
            "endTimeUnixNano": TraceTracer._unix_nanos(span.ended_at),
            "name": span.name,
            "parentSpanId": span.parent_span_id or "",
            "spanId": span.span_id,
            "startTimeUnixNano": TraceTracer._unix_nanos(span.started_at),
            "traceId": span.trace_id,
        }

    @staticmethod
    def _unix_nanos(timestamp: str | None) -> str:
        if timestamp is None:
            raise ValueError("completed spans must have an end timestamp")
        return str(int(datetime.fromisoformat(timestamp).timestamp() * 1_000_000_000))

    def clear(self) -> None:
        self._spans.clear()
