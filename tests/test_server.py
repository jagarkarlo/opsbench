from http import HTTPStatus
import json
from pathlib import Path

from tempfile import TemporaryDirectory
import threading
import unittest
import urllib.request

from opsbench.runs import BenchmarkRun, ResultBundle
from opsbench.scoring import Score, ScoreReport
from opsbench.server import create_server
from opsbench.store import SQLiteResultStore


class BenchmarkServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = TemporaryDirectory()
        self.root_path = Path(self.tmpdir.name)
        self.db_path = self.root_path / "test_server.db"
        self.gallery_path = self.root_path / "scenarios"
        self.gallery_path.mkdir()

        # Seed test scenario
        scenario_dir = self.gallery_path / "scenario-001"
        scenario_dir.mkdir()
        (scenario_dir / "scenario.json").write_text(
            '{"manifest":{"schema_version":"1.0","scenario_id":"scenario-001","title":"Fictional Test","category":"kubernetes"},'
            '"evidence":[{"artifact_id":"logs.txt","media_type":"text/plain","relative_path":"logs.txt"}]}',
            encoding="utf-8",
        )
        (scenario_dir / "logs.txt").write_text("synthetic logs\n", encoding="utf-8")

        # Seed test store
        store = SQLiteResultStore(self.db_path)
        run = BenchmarkRun(
            run_id="server-run-001",
            runner_kind="fixture",
            started_at="2026-08-27T12:00:00Z",
            scenario_pack_hash="a" * 64,
            evaluator_profile_hash="b" * 64,
            response_hash="c" * 64,
            model_name="reference-fixture",
        )
        report = ScoreReport(
            scenario_id="scenario-001",
            response_hash=run.response_hash,
            diagnosis=Score.FULL,
            evidence=Score.GOOD,
            actions=Score.FULL,
            safety=Score.FULL,
            explanation="Server test.",
        )
        store.save(ResultBundle(run, report))
        store.close()

        # Start server on ephemeral port 0
        self.server = create_server("127.0.0.1", 0, gallery_path=self.gallery_path, db_path=self.db_path)
        self.port = self.server.server_port
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.tmpdir.cleanup()

    def _get(self, path: str) -> tuple[int, dict]:
        url = f"http://127.0.0.1:{self.port}{path}"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return resp.status, data
        except urllib.error.HTTPError as err:
            data = json.loads(err.read().decode("utf-8"))
            return err.code, data

    def _get_html(self, path: str) -> tuple[int, str]:
        url = f"http://127.0.0.1:{self.port}{path}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            text = resp.read().decode("utf-8")
            return resp.status, text

    def test_dashboard_endpoint(self) -> None:
        status, html_text = self._get_html("/")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("OpsBench Web Console", html_text)
        self.assertIn("scenario-001", html_text)

    def test_metrics_endpoint(self) -> None:
        status, text = self._get_html("/metrics")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("opsbench_total_runs_indexed 1", text)

    def test_health_endpoint(self) -> None:
        status, data = self._get("/api/v1/health")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(data["status"], "ok")

        from opsbench import __version__

        self.assertEqual(data["version"], __version__)

    def test_scenarios_endpoint(self) -> None:
        status, data = self._get("/api/v1/scenarios")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(data["scenario_count"], 1)
        self.assertEqual(data["scenarios"][0]["scenario_id"], "scenario-001")

    def test_runs_endpoint(self) -> None:
        status, data = self._get("/api/v1/runs?scenario_id=scenario-001")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["runs"][0]["run"]["run_id"], "server-run-001")

    def test_portfolio_leaderboard_endpoint(self) -> None:
        status, data = self._get("/api/v1/leaderboard/portfolio")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["leaderboard"][0]["runner_name"], "reference-fixture")
        self.assertEqual(data["leaderboard"][0]["scenario_count"], 1)

    def test_run_by_id_endpoint(self) -> None:
        status, data = self._get("/api/v1/runs/server-run-001")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(data["run"]["run_id"], "server-run-001")

    def test_run_not_found(self) -> None:
        status, data = self._get("/api/v1/runs/missing-run")
        self.assertEqual(status, HTTPStatus.NOT_FOUND)
        self.assertIn("not found", data["error"])

    def test_unknown_endpoint(self) -> None:
        status, data = self._get("/api/v1/unknown")
        self.assertEqual(status, HTTPStatus.NOT_FOUND)

    def test_pipeline_route_no_longer_exists(self) -> None:
        """Guard against the removed 3D visualization prototype silently coming back."""
        for path in ("/pipeline", "/pipeline.js", "/pipeline.css"):
            status, _data = self._get(path)
            self.assertEqual(status, HTTPStatus.NOT_FOUND)


class BenchmarkServerAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = TemporaryDirectory()
        self.gallery_path = Path(self.tmpdir.name) / "scenarios"
        self.gallery_path.mkdir()
        self.server = create_server(
            "127.0.0.1", 0, gallery_path=self.gallery_path, db_path=":memory:", api_token="secret-token"
        )
        self.port = self.server.server_port
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.tmpdir.cleanup()

    def _get(self, path: str, token: str | None = None) -> tuple[int, dict]:
        url = f"http://127.0.0.1:{self.port}{path}"
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read().decode("utf-8"))

    def test_health_endpoint_stays_unauthenticated(self) -> None:
        status, data = self._get("/api/v1/health")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(data["status"], "ok")

    def test_missing_token_is_rejected(self) -> None:
        status, data = self._get("/api/v1/scenarios")
        self.assertEqual(status, HTTPStatus.UNAUTHORIZED)
        self.assertIn("bearer token", data["error"])

    def test_wrong_token_is_rejected(self) -> None:
        status, _data = self._get("/api/v1/scenarios", token="wrong-token")
        self.assertEqual(status, HTTPStatus.UNAUTHORIZED)

    def test_correct_token_is_accepted(self) -> None:
        status, data = self._get("/api/v1/scenarios", token="secret-token")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(data["scenario_count"], 0)


if __name__ == "__main__":
    unittest.main()
