import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
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

    def test_exports_completed_spans_to_an_otlp_http_endpoint(self) -> None:
        received: dict[str, str] = {}

        class CollectorHandler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                received["content_type"] = self.headers["Content-Type"]
                received["path"] = self.path
                length = int(self.headers["Content-Length"])
                received["body"] = self.rfile.read(length).decode("utf-8")
                self.send_response(200)
                self.end_headers()

            def log_message(self, format: str, *args: object) -> None:
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), CollectorHandler)
        thread = Thread(target=server.handle_request)
        thread.start()
        try:
            tracer = TraceTracer("opsbench-test")
            span = tracer.start_span("execute_run")
            tracer.end_span(span)

            tracer.export_otlp(f"http://127.0.0.1:{server.server_port}/v1/traces")
        finally:
            thread.join()
            server.server_close()

        payload = json.loads(received["body"])
        self.assertEqual(received["path"], "/v1/traces")
        self.assertEqual(received["content_type"], "application/json")
        self.assertEqual(
            payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["traceId"],
            span.trace_id,
        )

    def test_converts_timestamps_to_exact_unix_nanoseconds(self) -> None:
        unix_nanos = TraceTracer._unix_nanos("2026-09-02T12:34:56.123456+00:00")

        self.assertEqual(unix_nanos, "1788352496123456000")


if __name__ == "__main__":
    unittest.main()
