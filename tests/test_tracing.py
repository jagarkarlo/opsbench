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

    def test_completes_a_recorded_span(self) -> None:
        tracer = TraceTracer()
        span = tracer.start_span("execute_run")

        completed = tracer.end_span(span)

        self.assertIsNotNone(completed.ended_at)
        self.assertEqual(tracer.recorded_spans(), (completed,))
        self.assertEqual(tracer.end_span(completed), completed)

    def test_encodes_completed_spans_as_an_otlp_payload(self) -> None:
        tracer = TraceTracer("opsbench-test")
        span = tracer.start_span("execute_run", attributes={"scenario_id": "scenario-001"})
        tracer.end_span(span)

        payload = tracer.otlp_payload()

        resource_span = payload["resourceSpans"][0]
        exported_span = resource_span["scopeSpans"][0]["spans"][0]
        self.assertEqual(
            resource_span["resource"]["attributes"],
            [{"key": "service.name", "value": {"stringValue": "opsbench-test"}}],
        )
        self.assertEqual(exported_span["traceId"], span.trace_id)
        self.assertEqual(exported_span["spanId"], span.span_id)
        self.assertEqual(exported_span["attributes"], [
            {"key": "scenario_id", "value": {"stringValue": "scenario-001"}}
        ])
        self.assertTrue(exported_span["endTimeUnixNano"].isdigit())


if __name__ == "__main__":
    unittest.main()
