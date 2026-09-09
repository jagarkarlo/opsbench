"""Bounded test receiver for the disposable OpsBench verification lab."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path


EVENTS = Path("/data/events.jsonl")
EXPECTED_SUMMARY = os.environ.get("OPSBENCH_EXPECTED_SUMMARY", "OpsBench verification signal")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, {"status": "ok"})
            return
        if self.path == "/events":
            events = []
            if EVENTS.is_file():
                events = [json.loads(line) for line in EVENTS.read_text(encoding="utf-8").splitlines() if line]
            self._send(200, {"count": len(events), "events": events})
            return
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/alerts":
            self._send(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 64 * 1024:
            self._send(400, {"error": "bounded JSON body required"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send(400, {"error": "valid JSON required"})
            return
        if not isinstance(payload, dict) or not isinstance(payload.get("alerts"), list):
            self._send(400, {"error": "alert payload must contain an alerts array"})
            return
        for alert in payload["alerts"]:
            if not isinstance(alert, dict):
                self._send(400, {"error": "each alert must be an object"})
                return
            annotations = alert.get("annotations", {})
            if not isinstance(annotations, dict) or annotations.get("summary") != EXPECTED_SUMMARY:
                self._send(422, {"error": "invalid notification content"})
                return
        EVENTS.parent.mkdir(parents=True, exist_ok=True)
        with EVENTS.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, sort_keys=True) + "\n")
        self._send(202, {"accepted": True, "count": len(payload["alerts"])})

    def _send(self, status: int, data: dict) -> None:
        payload = json.dumps(data, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, _format: str, *_args: object) -> None:
        return


ThreadingHTTPServer(("0.0.0.0", 8090), Handler).serve_forever()
