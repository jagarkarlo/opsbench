"""Synthetic metric source for the disposable OpsBench verification lab."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os


MODE = os.environ.get("OPSBENCH_SIGNAL_MODE", "healthy")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, "ok\n", "text/plain")
            return
        if self.path == "/metrics":
            if MODE == "missing_collection":
                self._send(200, "# synthetic signal intentionally absent\n", "text/plain; version=0.0.4")
                return
            self._send(200, "opsbench_verification_signal 1\n", "text/plain; version=0.0.4")
            return
        self._send(404, "not found\n", "text/plain")

    def _send(self, status: int, body: str, content_type: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, _format: str, *_args: object) -> None:
        return


ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
