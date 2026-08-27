import unittest

from opsbench.tracing import TraceSpan, TraceTracer


class OpenTelemetryTracingTests(unittest.TestCase):
    def test_creates_and_records_trace_span(self) -> None:
        tracer = TraceTracer("test-service")
        span = tracer.start_span("execute_run", attributes={"scenario_id": "scenario-001"})

        self.assertEqual(span.name, "execute_run")
        self.assertEqual(span.to_dict()["attributes"], {"scenario_id": "scenario-001"})
        self.assertEqual(len(tracer.recorded_spans()), 1)

    def test_supports_parent_child_spans(self) -> None:
        tracer = TraceTracer()
        parent = tracer.start_span("suite_execution")
        child = tracer.start_span(
            "scenario_evaluation",
            trace_id=parent.trace_id,
            parent_span_id=parent.span_id,
        )

        self.assertEqual(child.trace_id, parent.trace_id)
        self.assertEqual(child.parent_span_id, parent.span_id)


if __name__ == "__main__":
    unittest.main()
