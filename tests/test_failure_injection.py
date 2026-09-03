from datetime import datetime, timezone
import unittest

from opsbench.adapters import FixtureResponseAdapter
from opsbench.failure_injection import (
    FailureInjection,
    FailureInjectingAdapter,
    FailureMode,
    InjectedFailureError,
)
from opsbench.responses import BenchmarkResponse
from opsbench.runner import execute_run
from opsbench.scenarios import EvidenceArtifact, ScenarioManifest, ScenarioPack
from opsbench.scoring import EvaluatorProfile, KeywordRule


class FailureInjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pack = ScenarioPack(
            ScenarioManifest("scenario-001", "Synthetic scenario", "kubernetes"),
            (EvidenceArtifact("logs.txt", "text/plain", b"synthetic logs"),),
        )
        self.profile = EvaluatorProfile(
            scenario_id="scenario-001",
            diagnosis_rules=(KeywordRule("synthetic", "synthetic"),),
        )
        self.adapter = FixtureResponseAdapter(
            BenchmarkResponse(
                "scenario-001",
                "Synthetic analysis.",
                cited_artifact_ids=("logs.txt",),
            )
        )

    def test_missing_evidence_is_deterministically_injected(self) -> None:
        adapter = FailureInjectingAdapter(
            self.adapter,
            FailureInjection(FailureMode.MISSING_EVIDENCE),
        )

        result = execute_run(
            run_id="failure-run-001",
            pack=self.pack,
            profile=self.profile,
            adapter=adapter,
            started_at=datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(result.run.runner_kind, "fixture+failure:missing_evidence")
        self.assertEqual(result.report.evidence, 1)
        self.assertIn("injected-missing-evidence", result.report.explanation)

    def test_exception_modes_are_deterministic(self) -> None:
        for mode, exception_type in (
            (FailureMode.TIMEOUT, TimeoutError),
            (FailureMode.MALFORMED_RESPONSE, ValueError),
            (FailureMode.ADAPTER_EXCEPTION, RuntimeError),
        ):
            with self.subTest(mode=mode):
                adapter = FailureInjectingAdapter(
                    self.adapter,
                    FailureInjection(mode, scenario_ids=("scenario-001",)),
                )
                with self.assertRaisesRegex(exception_type, f"injected {mode.value}"):
                    adapter.respond(self.pack)

    def test_exception_modes_do_not_call_wrapped_adapter(self) -> None:
        for mode in (
            FailureMode.TIMEOUT,
            FailureMode.MALFORMED_RESPONSE,
            FailureMode.ADAPTER_EXCEPTION,
        ):
            with self.subTest(mode=mode):
                adapter = FailureInjectingAdapter(
                    _FailIfCalledAdapter(),
                    FailureInjection(mode),
                )
                with self.assertRaises(InjectedFailureError):
                    adapter.respond(self.pack)

    def test_non_targeted_scenario_is_unchanged(self) -> None:
        injection = FailureInjection(FailureMode.MISSING_EVIDENCE, scenario_ids=("other",))
        response = FailureInjectingAdapter(self.adapter, injection).respond(self.pack)

        self.assertEqual(response.cited_artifact_ids, ("logs.txt",))


class _FailIfCalledAdapter:
    @property
    def adapter_name(self) -> str:
        return "fail-if-called"

    def respond(self, pack: ScenarioPack) -> BenchmarkResponse:
        raise AssertionError("wrapped adapter must not be called")


if __name__ == "__main__":
    unittest.main()