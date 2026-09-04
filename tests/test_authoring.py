from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from opsbench.authoring import ScenarioBuilder, scaffold_scenario
from opsbench.contribution import check_contribution, check_gallery_contributions
from opsbench.scenarios import load_scenario_pack
from opsbench.validator import lint_scenario

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BUILTIN_SCENARIOS = REPOSITORY_ROOT / "scenarios"


class ScenarioBuilderTests(unittest.TestCase):
    def test_builds_complete_scenario_pack(self) -> None:
        with TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "test-scenario-001"
            builder = ScenarioBuilder(
                scenario_id="kubernetes-ingress-001",
                title="Diagnose ingress 502 bad gateway",
                category="kubernetes",
            )
            builder.add_evidence(
                artifact_id="ingress.yaml",
                content="apiVersion: networking.k8s.io/v1\nkind: Ingress\n",
                media_type="text/yaml",
                relative_path="ingress.yaml",
            )
            builder.add_evidence(
                artifact_id="ingress-controller.log",
                content=b"2026-09-04 [error] upstream connect error: connection refused\n",
                media_type="text/plain",
            )
            builder.add_diagnosis_rule("connection refused", weight=2, rule_id="conn-err")
            builder.add_expected_action("check backend service health")
            builder.add_blocked_phrase("delete namespace")
            builder.set_reference_response(
                analysis="Ingress returns 502 because of connection refused from the backend service.",
                cited_artifact_ids=["ingress-controller.log"],
                proposed_actions=["check backend service health"],
            )

            created_path = builder.build(dest)
            self.assertEqual(created_path, dest)
            self.assertTrue((dest / "scenario.json").is_file())
            self.assertTrue((dest / "evaluator.json").is_file())
            self.assertTrue((dest / "ingress.yaml").is_file())
            self.assertTrue((dest / "ingress-controller.log").is_file())
            self.assertTrue((dest / "responses" / "reference-response.json").is_file())

            # Load pack through normal scenario loader
            pack = load_scenario_pack(dest)
            self.assertEqual(pack.manifest.scenario_id, "kubernetes-ingress-001")
            self.assertEqual(len(pack.evidence), 2)

    def test_builder_rejects_duplicate_artifacts_or_keywords(self) -> None:
        builder = ScenarioBuilder(
            scenario_id="database-pool-001",
            title="Database connection pool exhaustion",
            category="database",
        )
        builder.add_evidence("db.log", "some log content")
        with self.assertRaisesRegex(ValueError, "duplicate artifact_id"):
            builder.add_evidence("db.log", "other content")

        builder.add_diagnosis_rule("pool timeout", weight=1)
        with self.assertRaisesRegex(ValueError, "duplicate diagnosis keyword"):
            builder.add_diagnosis_rule("pool timeout", weight=2)

    def test_builder_validates_manifest_fields_and_empty_rules(self) -> None:
        with self.assertRaisesRegex(ValueError, "category must be one of"):
            ScenarioBuilder(
                scenario_id="invalid-cat-001",
                title="Invalid Category",
                category="networking",
            )

        builder = ScenarioBuilder(
            scenario_id="gitops-sync-001",
            title="GitOps sync error",
            category="gitops",
        )
        with TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "gitops-sync-001"
            with self.assertRaisesRegex(ValueError, "at least one evidence artifact"):
                builder.build(dest)

            builder.add_evidence("app.yaml", "metadata:\n  name: app\n")
            with self.assertRaisesRegex(ValueError, "at least one diagnosis rule"):
                builder.build(dest)

    def test_builder_prevents_overwrite_unless_requested(self) -> None:
        with TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "existing-dir"
            dest.mkdir()
            builder = ScenarioBuilder("terraform-drift-001", "Terraform drift", "terraform")
            builder.add_evidence("main.tf", 'resource "null_resource" "test" {}\n')
            builder.add_diagnosis_rule("drift detected")

            with self.assertRaises(FileExistsError):
                builder.build(dest, overwrite=False)

            created = builder.build(dest, overwrite=True)
            self.assertEqual(created, dest)


class ScaffoldScenarioTests(unittest.TestCase):
    def test_scaffolds_turnkey_valid_scenario(self) -> None:
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "observability-trace-001"
            scaffold_scenario(
                scenario_id="observability-trace-001",
                title="Diagnose dropped trace spans",
                category="observability",
                destination=target,
            )

            self.assertEqual(lint_scenario(target), [])
            check_result = check_contribution(target)
            self.assertTrue(check_result.passed)
            self.assertEqual(check_result.issues, ())


class ContributionCheckTests(unittest.TestCase):
    def test_builtin_scenarios_pass_contribution_checks(self) -> None:
        results = check_gallery_contributions(BUILTIN_SCENARIOS)
        self.assertGreater(len(results), 0)
        for res in results:
            self.assertTrue(res.passed, f"Failed contribution checks for {res.scenario_id}: {res.issues}")

    def test_detects_invalid_naming_convention(self) -> None:
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "bad_id"
            builder = ScenarioBuilder("kubernetes_Bad_ID", "Bad ID", "kubernetes")
            builder.add_evidence("service.log", "sample log content that is long enough")
            builder.add_diagnosis_rule("sample error keyword")
            builder.set_reference_response("sample error keyword in analysis")
            builder.build(target)

            result = check_contribution(target)
            self.assertFalse(result.passed)
            self.assertTrue(any("recommended lower-case alphanumeric" in issue for issue in result.issues))

    def test_detects_too_short_evidence(self) -> None:
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "database-short-001"
            builder = ScenarioBuilder("database-short-001", "Short evidence", "database")
            builder.add_evidence("tiny.log", "tiny")  # < 10 bytes
            builder.add_diagnosis_rule("tiny error")
            builder.set_reference_response("tiny error occurs")
            builder.build(target)

            result = check_contribution(target)
            self.assertFalse(result.passed)
            self.assertTrue(any("evidence artifact 'tiny.log' content is too short" in issue for issue in result.issues))

    def test_detects_failing_reference_response(self) -> None:
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "terraform-fail-ref-001"
            builder = ScenarioBuilder("terraform-fail-ref-001", "Failing reference response", "terraform")
            builder.add_evidence("plan.txt", "Terraform will perform the following actions: apply\n")
            builder.add_diagnosis_rule("cyclic dependency error")
            # Analysis does NOT contain the keyword, so score will be 0
            builder.set_reference_response("Everything looks completely fine and healthy.")
            builder.build(target)

            result = check_contribution(target)
            self.assertFalse(result.passed)
            self.assertTrue(any("no reference response achieved a passing diagnosis score" in issue for issue in result.issues))

    def test_detects_leaked_credentials(self) -> None:
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "kubernetes-leak-001"
            builder = ScenarioBuilder("kubernetes-leak-001", "Credential leak", "kubernetes")
            builder.add_evidence(
                "pod.log",
                "2026-09-04 [error] failed connecting with key: -----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...",
            )
            builder.add_diagnosis_rule("failed connecting with key")
            builder.set_reference_response("The pod log shows failed connecting with key.")
            builder.build(target)

            result = check_contribution(target)
            self.assertFalse(result.passed)
            self.assertTrue(any("prohibited secret leak detected in pod.log: private key header" in issue for issue in result.issues))


if __name__ == "__main__":
    unittest.main()
