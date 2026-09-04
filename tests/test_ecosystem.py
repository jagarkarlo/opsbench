from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from opsbench.attestation import (
    load_attestation,
    sign_result_bundle,
    verify_result_attestation,
    write_attestation,
)
from opsbench.cli import main
from opsbench.datasets import (
    PublicDatasetManifest,
    export_public_dataset,
    load_public_dataset,
    verify_public_dataset,
)
from opsbench.runs import BenchmarkRun, ResultBundle
from opsbench.scoring import Score, ScoreReport


class EcosystemTests(unittest.TestCase):
    def build_bundle(self) -> ResultBundle:
        run = BenchmarkRun(
            run_id="attestation-run-001",
            runner_kind="fixture",
            started_at="2026-09-04T12:00:00Z",
            scenario_pack_hash="a" * 64,
            evaluator_profile_hash="b" * 64,
            response_hash="c" * 64,
        )
        report = ScoreReport(
            scenario_id="scenario-001",
            response_hash="c" * 64,
            diagnosis=Score.GOOD,
            evidence=Score.FULL,
            actions=Score.LOW,
            safety=Score.FULL,
            explanation="synthetic attestation result",
        )
        return ResultBundle(run, report)

    def test_attestation_round_trip_and_wrong_key(self) -> None:
        bundle = self.build_bundle()
        attestation = sign_result_bundle(
            bundle,
            "test-key",
            "ci@example.invalid",
            metadata={"purpose": "test"},
            timestamp_utc="2026-09-04T12:01:00+00:00",
        )

        self.assertTrue(verify_result_attestation(bundle, attestation, "test-key"))
        self.assertFalse(verify_result_attestation(bundle, attestation, "wrong-key"))
        self.assertEqual(attestation.metadata["purpose"], "test")

        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "attestation.json"
            write_attestation(path, attestation)
            self.assertEqual(load_attestation(path), attestation)

        with self.assertRaisesRegex(ValueError, "SHA-256 hex digest"):
            attestation.__class__("z" * 64, "signer", "2026-09-04T12:00:00Z", "signature")

    def test_dataset_manifest_rejects_non_hex_checksum(self) -> None:
        with self.assertRaisesRegex(ValueError, "SHA-256 hex digest"):
            PublicDatasetManifest(
                dataset_name="test",
                version="1.0",
                created_at_utc="2026-09-04T12:00:00Z",
                scenario_count=0,
                scenarios=(),
                checksum="z" * 64,
            )

    def test_dataset_export_and_gallery_verification(self) -> None:
        gallery_path = Path(__file__).parents[1] / "scenarios"
        with TemporaryDirectory() as temporary_directory:
            dataset_path = Path(temporary_directory) / "dataset.json"
            manifest = export_public_dataset(
                gallery_path,
                dataset_path,
                dataset_name="test-gallery",
                version="0.1",
                timestamp_utc="2026-09-04T12:00:00+00:00",
            )

            self.assertEqual(load_public_dataset(dataset_path), manifest)
            self.assertEqual(verify_public_dataset(dataset_path, gallery_path), (True, []))

            payload = json.loads(dataset_path.read_text(encoding="utf-8"))
            payload["scenarios"][0]["title"] = "tampered"
            dataset_path.write_text(json.dumps(payload), encoding="utf-8")
            verified, issues = verify_public_dataset(dataset_path)
            self.assertFalse(verified)
            self.assertTrue(any("checksum mismatch" in issue for issue in issues))

    def test_attest_and_dataset_cli_commands(self) -> None:
        bundle = self.build_bundle()
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            bundle_path = directory / "bundle.json"
            bundle_path.write_text(bundle.canonical_json() + "\n", encoding="utf-8")
            attestation_path = directory / "attestation.json"

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    main(
                        [
                            "attest",
                            "sign",
                            str(bundle_path),
                            str(attestation_path),
                            "--key",
                            "test-key",
                            "--signer",
                            "ci@example.invalid",
                        ]
                    ),
                    0,
                )
            self.assertEqual(json.loads(output.getvalue())["status"], "signed")

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    main(
                        [
                            "attest",
                            "verify",
                            str(bundle_path),
                            str(attestation_path),
                            "--key",
                            "test-key",
                        ]
                    ),
                    0,
                )
            self.assertTrue(json.loads(output.getvalue())["verified"])

            dataset_path = directory / "dataset.json"
            gallery_path = Path(__file__).parents[1] / "scenarios"
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    main(
                        [
                            "dataset",
                            "export",
                            str(gallery_path),
                            str(dataset_path),
                            "--name",
                            "cli-gallery",
                        ]
                    ),
                    0,
                )
            self.assertEqual(json.loads(output.getvalue())["status"], "exported")

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    main(
                        ["dataset", "verify", str(dataset_path), "--gallery-path", str(gallery_path)]
                    ),
                    0,
                )
            self.assertTrue(json.loads(output.getvalue())["verified"])


if __name__ == "__main__":
    unittest.main()
