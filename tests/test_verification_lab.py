from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).parents[1]
LAB = ROOT / "deploy" / "verification"


class VerificationLabAssetTests(unittest.TestCase):
    def test_lab_contains_the_four_real_components(self) -> None:
        compose = (LAB / "docker-compose.yml").read_text(encoding="utf-8")

        for service in ("test-service:", "prometheus:", "alertmanager:", "receiver:"):
            self.assertIn(service, compose)
        self.assertIn("receiver-events:", compose)
        self.assertIn("condition: service_healthy", compose)

    def test_prometheus_and_alertmanager_are_connected_to_the_receiver(self) -> None:
        prometheus = (LAB / "prometheus.yml").read_text(encoding="utf-8")
        alertmanager = (LAB / "alertmanager.yml").read_text(encoding="utf-8")
        rules = (LAB / "rules.yml").read_text(encoding="utf-8")

        self.assertIn("test-service:8000", prometheus)
        self.assertIn("alertmanager:9093", prometheus)
        self.assertIn("receiver:8090/alerts", alertmanager)
        self.assertIn("opsbench_verification_signal == 1", rules)

    def test_failure_modes_and_cleanup_are_declared(self) -> None:
        service = (LAB / "test_service.py").read_text(encoding="utf-8")
        receiver = (LAB / "receiver.py").read_text(encoding="utf-8")
        smoke = (ROOT / "scripts" / "verification_lab_smoke.sh").read_text(encoding="utf-8")

        self.assertIn("missing_collection", service)
        self.assertIn("invalid notification content", receiver)
        self.assertIn("healthy|missing_collection|invalid_notification", smoke)
        self.assertIn("down -v --remove-orphans", smoke)
        self.assertIn("verify monitoring-path", smoke)

    def test_compose_config_and_shell_syntax_are_valid(self) -> None:
        compose_check = subprocess.run(
            ["docker", "compose", "-f", str(LAB / "docker-compose.yml"), "config", "--quiet"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(compose_check.returncode, 0, compose_check.stderr)
        shell_check = subprocess.run(
            ["bash", "-n", str(ROOT / "scripts" / "verification_lab_smoke.sh")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(shell_check.returncode, 0, shell_check.stderr)


if __name__ == "__main__":
    unittest.main()