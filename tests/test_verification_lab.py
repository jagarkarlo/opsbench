from pathlib import Path
import importlib.util
import json
import subprocess
from tempfile import TemporaryDirectory
import unittest

from opsbench.verification import evaluate_verification, load_verification_input


ROOT = Path(__file__).parents[1]
LAB = ROOT / "deploy" / "verification"
_spec = importlib.util.spec_from_file_location("verification_lab_observe", ROOT / "scripts" / "verification_lab_observe.py")
observe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(observe)

HEALTHY_SNAPSHOT = {
    "metrics_body": "# HELP synthetic\nopsbench_verification_signal 1\n",
    "target": {"health": "up"},
    "signal_values": ["1"],
    "rule_state": "firing",
    "alert_receivers": ["opsbench-test-receiver"],
    "accepted": 1,
    "rejected": 0,
}
MODE_SNAPSHOTS = {
    "healthy": HEALTHY_SNAPSHOT,
    "missing_collection": {
        "metrics_body": "opsbench_verification_signal 1\n",
        "target": {"health": "down", "lastError": "connection refused"},
    },
    "routing_mismatch": {**HEALTHY_SNAPSHOT, "alert_receivers": ["opsbench-null"], "accepted": 0},
    "invalid_notification": {**HEALTHY_SNAPSHOT, "accepted": 0, "rejected": 2},
    "unavailable": {"metrics_body": None},
}
EXPECTED_OUTCOMES = {
    "healthy": "passed",
    "missing_collection": "failed",
    "routing_mismatch": "failed",
    "invalid_notification": "failed",
    "unavailable": "unknown",
}
NOW = "2026-09-23T12:00:00Z"


def statuses(observations: list[dict]) -> tuple[str, ...]:
    return tuple(observation["status"] for observation in observations)


class VerificationLabObserverTests(unittest.TestCase):
    def test_each_mode_snapshot_classifies_to_its_expected_stages(self) -> None:
        self.assertEqual(set(MODE_SNAPSHOTS), set(observe.EXPECTED))
        for mode, snapshot in MODE_SNAPSHOTS.items():
            with self.subTest(mode=mode):
                observations = observe.classify(snapshot, final=False, observed_at=NOW)
                self.assertEqual(statuses(observations), observe.EXPECTED[mode])

    def test_observations_satisfy_the_verification_contract(self) -> None:
        for mode, snapshot in MODE_SNAPSHOTS.items():
            with self.subTest(mode=mode), TemporaryDirectory() as directory:
                observations = observe.classify(snapshot, final=False, observed_at=NOW)
                path = Path(directory) / "input.json"
                path.write_text(json.dumps(observe.build_input(mode, NOW, observations)), encoding="utf-8")
                report = evaluate_verification(load_verification_input(path))
                self.assertEqual(report.outcome, EXPECTED_OUTCOMES[mode])

    def test_pending_stage_waits_then_times_out_as_unknown(self) -> None:
        snapshot = {**HEALTHY_SNAPSHOT, "rule_state": "pending"}

        self.assertIsNone(observe.classify(snapshot, final=False, observed_at=NOW))
        observations = observe.classify(snapshot, final=True, observed_at=NOW)

        self.assertEqual(statuses(observations), ("passed", "passed", "unknown", "not_tested", "not_tested"))
        self.assertIsNone(observations[2]["observed_at"])
        self.assertIn("deadline", observations[2]["summary"])

    def test_scrape_target_not_yet_reported_is_pending_not_failed(self) -> None:
        snapshot = {"metrics_body": "opsbench_verification_signal 1\n"}
        self.assertIsNone(observe.classify(snapshot, final=False, observed_at=NOW))

    def test_signal_absent_from_source_fails_emission(self) -> None:
        observations = observe.classify({"metrics_body": "# nothing\n"}, final=False, observed_at=NOW)
        self.assertEqual(observations[0]["status"], "failed")
        self.assertEqual(statuses(observations)[1:], ("not_tested",) * 4)


class VerificationLabAssetTests(unittest.TestCase):
    def test_lab_contains_the_four_real_components(self) -> None:
        compose = (LAB / "docker-compose.yml").read_text(encoding="utf-8")

        for service in ("test-service:", "prometheus:", "alertmanager:", "receiver:"):
            self.assertIn(service, compose)
        self.assertIn("receiver-events:", compose)
        self.assertIn("condition: service_healthy", compose)

    def test_failure_overlays_replace_exactly_one_component_config(self) -> None:
        overlays = {
            "missing-collection": ("prometheus-missing-collection.yml", "/etc/prometheus/prometheus.yml"),
            "invalid-notification": ("rules-invalid-notification.yml", "/etc/prometheus/rules.yml"),
            "routing-mismatch": ("alertmanager-routing-mismatch.yml", "/etc/alertmanager/alertmanager.yml"),
        }
        for name, (source, target) in overlays.items():
            with self.subTest(overlay=name):
                self.assertTrue((LAB / source).is_file())
                overlay = (LAB / f"docker-compose.{name}.yml").read_text(encoding="utf-8")
                self.assertIn(f"./{source}:{target}:ro", overlay)
        self.assertIn("test-service:8001", (LAB / "prometheus-missing-collection.yml").read_text(encoding="utf-8"))
        routing = (LAB / "alertmanager-routing-mismatch.yml").read_text(encoding="utf-8")
        self.assertIn("receiver: opsbench-null", routing)
        self.assertIn('severity="critical"', routing)

    def test_prometheus_and_alertmanager_are_connected_to_the_receiver(self) -> None:
        prometheus = (LAB / "prometheus.yml").read_text(encoding="utf-8")
        alertmanager = (LAB / "alertmanager.yml").read_text(encoding="utf-8")
        rules = (LAB / "rules.yml").read_text(encoding="utf-8")

        self.assertIn("test-service:8000", prometheus)
        self.assertIn("alertmanager:9093", prometheus)
        self.assertIn("receiver:8090/alerts", alertmanager)
        self.assertIn("opsbench_verification_signal == 1", rules)

    def test_harness_declares_modes_and_verified_cleanup(self) -> None:
        receiver = (LAB / "receiver.py").read_text(encoding="utf-8")
        smoke = (ROOT / "scripts" / "verification_lab_smoke.sh").read_text(encoding="utf-8")

        self.assertIn("invalid notification content", receiver)
        self.assertIn('"rejected": REJECTED', receiver)
        self.assertIn("healthy|missing_collection|routing_mismatch|invalid_notification|unavailable", smoke)
        self.assertIn("stop test-service", smoke)
        self.assertIn("trap 'exit 130' INT TERM", smoke)
        self.assertIn("down -v --remove-orphans", smoke)
        self.assertIn("cleanup verified", smoke)
        self.assertIn("verify monitoring-path", smoke)

    def test_release_metadata_is_synchronized(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        package = (ROOT / "src" / "opsbench" / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('version = "0.8.0"', pyproject)
        self.assertIn('__version__ = "0.8.0"', package)

    def test_compose_config_and_shell_syntax_are_valid(self) -> None:
        compose_check = subprocess.run(
            ["docker", "compose", "-f", str(LAB / "docker-compose.yml"), "config", "--quiet"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(compose_check.returncode, 0, compose_check.stderr)
        for overlay in sorted(LAB.glob("docker-compose.*.yml")):
            overlay_check = subprocess.run(
                ["docker", "compose", "-f", str(LAB / "docker-compose.yml"), "-f", str(overlay), "config", "--quiet"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(overlay_check.returncode, 0, overlay_check.stderr)
        shell_check = subprocess.run(
            ["bash", "-n", str(ROOT / "scripts" / "verification_lab_smoke.sh")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(shell_check.returncode, 0, shell_check.stderr)


if __name__ == "__main__":
    unittest.main()