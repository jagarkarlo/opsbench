"""Zero-dependency HTTP API server for OpsBench platform services."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from opsbench.metrics import generate_prometheus_metrics
from opsbench.comparisons import rank_portfolio
from opsbench.scenarios import load_gallery
from opsbench.store import RunQuery, SQLiteResultStore
from opsbench.web import render_dashboard_html


class BenchmarkRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OpsBench REST API endpoints."""

    gallery_path: Path = Path("scenarios")
    db_path: Path | str = ":memory:"
    api_token: str | None = None
    frontend_path: Path | None = None

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

        if path in ("/app", "/app/") or path.startswith("/app/assets/"):
            if self.frontend_path is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "frontend build not configured"})
                return
            relative_path = path[len("/app/") :] if path.startswith("/app/") else "index.html"
            asset_path = (self.frontend_path / relative_path).resolve()
            root_path = self.frontend_path.resolve()
            if root_path not in asset_path.parents and asset_path != root_path:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid frontend path"})
                return
            if not asset_path.is_file():
                asset_path = root_path / "index.html"
            try:
                self._send_text(
                    HTTPStatus.OK,
                    asset_path.read_text(encoding="utf-8"),
                    mimetypes.guess_type(str(asset_path))[0] or "text/html; charset=utf-8",
                )
            except OSError as error:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})
            return

        if path == "/api/v1/health":
            from opsbench import __version__  # local import: opsbench.__init__ imports this module

            self._send_json(HTTPStatus.OK, {"status": "ok", "version": __version__})
            return

        if path == "/api/v1/capabilities":
            self._send_json(
                HTTPStatus.OK,
                {
                    "frontend": self.frontend_path is not None,
                    "operations": [
                        {"id": "scenario-gallery", "label": "Scenario gallery", "mode": "ui"},
                        {"id": "run-inspection", "label": "Indexed run inspection", "mode": "ui"},
                        {"id": "portfolio-leaderboard", "label": "Portfolio leaderboard", "mode": "ui"},
                        {"id": "benchmark-execution", "label": "Benchmark execution", "mode": "cli"},
                        {"id": "response-evaluation", "label": "Response evaluation", "mode": "cli"},
                        {"id": "store-management", "label": "Store backup and restore", "mode": "cli"},
                        {"id": "integrity-attestation", "label": "Dataset and attestation workflows", "mode": "cli"},
                        {"id": "mcp-context", "label": "MCP context inspection", "mode": "cli"},
                    ],
                },
            )
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

        if path == "/api/v1/leaderboard/portfolio":
            limit_str = query_params.get("limit", ["500"])[0]
            try:
                limit = int(limit_str)
            except ValueError:
                limit = 500
            store = SQLiteResultStore(self.db_path)
            try:
                rankings = rank_portfolio(store.query(RunQuery(limit=limit)))
                data = {
                    "count": len(rankings),
                    "leaderboard": [
                        {
                            "average_score": statistic.average_score,
                            "confidence_interval_95": list(statistic.confidence_interval_95),
                            "conservative_score": statistic.conservative_score,
                            "runner_name": statistic.runner_name,
                            "scenario_count": statistic.scenario_count,
                            "standard_deviation": statistic.standard_deviation,
                            "trial_count": statistic.trial_count,
                        }
                        for statistic in rankings
                    ],
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
    frontend_path: Path | None = None,
) -> HTTPServer:
    """Create a configured OpsBench HTTPServer instance."""
    class_handler = type(
        "ConfiguredBenchmarkRequestHandler",
        (BenchmarkRequestHandler,),
        {
            "gallery_path": gallery_path,
            "db_path": db_path,
            "api_token": api_token,
            "frontend_path": frontend_path,
        },
    )
    return HTTPServer((host, port), class_handler)
