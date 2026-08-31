"""Zero-dependency HTTP API server for OpsBench platform services."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from opsbench.metrics import generate_prometheus_metrics
from opsbench.scenarios import load_gallery
from opsbench.store import RunQuery, SQLiteResultStore
from opsbench.web import render_dashboard_html


class BenchmarkRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OpsBench REST API endpoints."""

    gallery_path: Path = Path("scenarios")
    db_path: Path | str = ":memory:"
    api_token: str | None = None

    def _is_authorized(self) -> bool:
        """Return True when no token is configured or the request presents a matching bearer token."""
        if not self.api_token:
            return True
        header = self.headers.get("Authorization", "")
        prefix = "Bearer "
        if not header.startswith(prefix):
            return False
        return header[len(prefix) :] == self.api_token

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path.rstrip("/")
        if not path:
            path = "/"

        query_params = parse_qs(parsed_url.query)

        if path != "/api/v1/health" and not self._is_authorized():
            self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "missing or invalid bearer token"})
            return

        if path in ("/", "/dashboard"):
            store = SQLiteResultStore(self.db_path)
            try:
                html_text = render_dashboard_html(store)
                self._send_html(HTTPStatus.OK, html_text)
            except Exception as error:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})
            finally:
                store.close()
            return

        if path == "/api/v1/health":
            self._send_json(HTTPStatus.OK, {"status": "ok", "version": "0.1.0"})
            return

        if path == "/metrics":
            store = SQLiteResultStore(self.db_path)
            try:
                metrics_text = generate_prometheus_metrics(store)
                self._send_text(HTTPStatus.OK, metrics_text, "text/plain; version=0.0.4; charset=utf-8")
            except Exception as error:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})
            finally:
                store.close()
            return

        if path == "/api/v1/scenarios":
            try:
                gallery = load_gallery(self.gallery_path)
                data = {
                    "scenario_count": len(gallery.scenarios),
                    "scenarios": [
                        {
                            "category": scenario.manifest.category,
                            "pack_hash": scenario.content_hash(),
                            "scenario_id": scenario.manifest.scenario_id,
                            "title": scenario.manifest.title,
                        }
                        for scenario in gallery.scenarios
                    ],
                }
                self._send_json(HTTPStatus.OK, data)
            except Exception as error:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})
            return

        if path == "/api/v1/runs":
            scenario_id = query_params.get("scenario_id", [None])[0]
            runner_kind = query_params.get("runner_kind", [None])[0]
            model_name = query_params.get("model_name", [None])[0]
            limit_str = query_params.get("limit", ["100"])[0]
            try:
                limit = int(limit_str)
            except ValueError:
                limit = 100

            store = SQLiteResultStore(self.db_path)
            try:
                bundles = store.query(
                    RunQuery(
                        scenario_id=scenario_id,
                        runner_kind=runner_kind,
                        model_name=model_name,
                        limit=limit,
                    )
                )
                data = {
                    "count": len(bundles),
                    "runs": [bundle.to_dict() for bundle in bundles],
                }
                self._send_json(HTTPStatus.OK, data)
            except Exception as error:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})
            finally:
                store.close()
            return

        if path.startswith("/api/v1/runs/"):
            run_id = path[len("/api/v1/runs/") :]
            if not run_id:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "run_id required"})
                return

            store = SQLiteResultStore(self.db_path)
            try:
                bundle = store.get(run_id)
                if bundle is None:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": f"run {run_id!r} not found"})
                else:
                    self._send_json(HTTPStatus.OK, bundle.to_dict())
            except Exception as error:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})
            finally:
                store.close()
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "endpoint not found"})

    def _send_json(self, status: int, data: dict[str, Any]) -> None:
        body = json.dumps(data, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status: int, html_text: str) -> None:
        self._send_text(status, html_text, "text/html; charset=utf-8")

    def _send_text(self, status: int, text: str, content_type: str) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP server stderr logging in tests."""
        pass


def create_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    gallery_path: Path = Path("scenarios"),
    db_path: Path | str = ":memory:",
    api_token: str | None = None,
) -> HTTPServer:
    """Create a configured OpsBench HTTPServer instance."""
    class_handler = type(
        "ConfiguredBenchmarkRequestHandler",
        (BenchmarkRequestHandler,),
        {"gallery_path": gallery_path, "db_path": db_path, "api_token": api_token},
    )
    return HTTPServer((host, port), class_handler)
