from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from opsbench.responses import BenchmarkResponse
from opsbench.scenarios import (
    EvidenceArtifact,
    ScenarioManifest,
    ScenarioPack,
)
from opsbench.specialized_adapters import (
    ColdRouteAdapter,
    ColdRouteProfile,
    ReliabilityReplayAdapter,
    ReliabilityReplayTimeline,
    ReplayStep,
    load_cold_routes,
    load_replay_timeline,
    write_cold_routes,
    write_replay_timeline,
)


class SpecializedAdaptersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = ScenarioManifest(
            scenario_id="kubernetes-coredns-001",
            title="CoreDNS failure",
            category="kubernetes",
        )
        self.evidence = (
            EvidenceArtifact("coredns.log", "text/plain", b"upstream timed out\n"),
            EvidenceArtifact("events.json", "application/json", b"[]\n"),
        )
        self.pack = ScenarioPack(
            manifest=self.manifest,
            evidence=self.evidence,
        )

    def test_replay_step_validation_and_serialization(self) -> None:
        step = ReplayStep(
            step_number=1,
            elapsed_seconds=12.5,
            event_type="alert_fired",
            summary="CoreDNS upstream latency high",
            artifact_id="coredns.log",
            action_taken="checked resolv.conf",
        )
        data = step.to_dict()
        self.assertEqual(data["step_number"], 1)
        self.assertEqual(data["artifact_id"], "coredns.log")

        restored = ReplayStep.from_dict(data)
        self.assertEqual(restored.step_number, 1)
        self.assertEqual(restored.summary, "CoreDNS upstream latency high")
        self.assertEqual(restored.action_taken, "checked resolv.conf")

        with self.assertRaises(ValueError):
            ReplayStep(0, 1.0, "type", "summary")
        with self.assertRaises(ValueError):
            ReplayStep(1, -1.0, "type", "summary")
        with self.assertRaises(ValueError):
            ReplayStep(1, 1.0, "", "summary")

    def test_replay_timeline_serialization_and_disk_roundtrip(self) -> None:
        timeline = ReliabilityReplayTimeline(
            scenario_id="kubernetes-coredns-001",
            initial_symptoms="Pods failing name resolution",
            root_cause_analysis="Upstream nameserver unreachable from worker nodes",
            steps=(
                ReplayStep(1, 0.0, "detection", "Alert triggered for DNS resolution timeout"),
                ReplayStep(2, 45.0, "investigation", "Inspected CoreDNS pods", artifact_id="coredns.log"),
            ),
            resolution_actions=("restart coredns", "update resolv.conf"),
        )

        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "timeline.json"
            write_replay_timeline(file_path, timeline)
            loaded = load_replay_timeline(file_path)

            self.assertEqual(loaded.scenario_id, timeline.scenario_id)
            self.assertEqual(len(loaded.steps), 2)
            self.assertEqual(loaded.steps[1].artifact_id, "coredns.log")
            self.assertEqual(loaded.resolution_actions, ("restart coredns", "update resolv.conf"))

    def test_replay_adapter_responds_with_evidence_and_narrative(self) -> None:
        timeline = ReliabilityReplayTimeline(
            scenario_id="kubernetes-coredns-001",
            initial_symptoms="Pods failing name resolution",
            root_cause_analysis="Upstream nameserver unreachable",
            steps=(
                ReplayStep(1, 0.0, "detection", "Resolution timeout", artifact_id="coredns.log"),
                ReplayStep(2, 30.0, "action", "Cluster restart", artifact_id="nonexistent.txt"),
            ),
            resolution_actions=("restart coredns",),
        )

        adapter = ReliabilityReplayAdapter(timeline)
        self.assertEqual(adapter.adapter_name, "reliability-replay")

        resp = adapter.respond(self.pack)
        self.assertEqual(resp.scenario_id, "kubernetes-coredns-001")
        self.assertIn("Upstream nameserver unreachable", resp.analysis)
        self.assertIn("Step 1 (detection): Resolution timeout", resp.analysis)
        # nonexistent.txt should not be cited since it is not in the pack's evidence
        self.assertEqual(resp.cited_artifact_ids, ("coredns.log",))
        self.assertEqual(resp.proposed_actions, ("restart coredns",))

    def test_replay_adapter_rejects_mismatched_scenario(self) -> None:
        timeline = ReliabilityReplayTimeline(
            scenario_id="other-scenario-002",
            initial_symptoms="symptoms",
            root_cause_analysis="rca",
            steps=(ReplayStep(1, 0.0, "step", "desc"),),
            resolution_actions=(),
        )
        adapter = ReliabilityReplayAdapter(timeline)
        with self.assertRaisesRegex(ValueError, "does not match pack"):
            adapter.respond(self.pack)

    def test_cold_route_profile_serialization(self) -> None:
        profile = ColdRouteProfile(
            route_id="dr-failover-weu",
            target_environment="azure-weu-secondary",
            last_verified_timestamp="2026-09-01T00:00:00Z",
            warmup_duration_seconds=120.0,
            fallback_actions=("activate failover dns", "scale cold pods"),
        )
        data = profile.to_dict()
        restored = ColdRouteProfile.from_dict(data)
        self.assertEqual(restored.route_id, "dr-failover-weu")
        self.assertEqual(restored.warmup_duration_seconds, 120.0)

        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "routes.json"
            write_cold_routes(file_path, [profile])
            loaded = load_cold_routes(file_path)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].route_id, "dr-failover-weu")

    def test_cold_route_adapter_activates_matching_route(self) -> None:
        profile = ColdRouteProfile(
            route_id="coredns",
            target_environment="cluster-internal-dns-fallback",
            last_verified_timestamp="2026-09-04T00:00:00Z",
            warmup_duration_seconds=15.0,
            fallback_actions=("route traffic to secondary dns",),
        )

        def mock_provider(pack: ScenarioPack) -> BenchmarkResponse:
            return BenchmarkResponse(
                scenario_id=pack.manifest.scenario_id,
                analysis="Primary DNS latency issue diagnosed.",
                cited_artifact_ids=("coredns.log",),
                proposed_actions=("scale coredns",),
            )

        adapter = ColdRouteAdapter([profile], mock_provider)
        self.assertEqual(adapter.adapter_name, "cold-route")

        resp = adapter.respond(self.pack)
        self.assertIn("ColdRoute Activated", resp.analysis)
        self.assertIn("cluster-internal-dns-fallback", resp.analysis)
        self.assertEqual(
            resp.proposed_actions,
            ("scale coredns", "route traffic to secondary dns"),
        )

    def test_cold_route_adapter_passes_through_non_matching_scenario(self) -> None:
        profile = ColdRouteProfile(
            route_id="unrelated-route",
            target_environment="other-env",
            last_verified_timestamp=None,
            warmup_duration_seconds=0.0,
            fallback_actions=(),
        )

        def mock_provider(pack: ScenarioPack) -> BenchmarkResponse:
            return BenchmarkResponse(
                scenario_id=pack.manifest.scenario_id,
                analysis="Standard diagnosis.",
            )

        adapter = ColdRouteAdapter([profile], mock_provider)
        resp = adapter.respond(self.pack)
        self.assertNotIn("ColdRoute Activated", resp.analysis)
        self.assertEqual(resp.analysis, "Standard diagnosis.")


if __name__ == "__main__":
    unittest.main()
