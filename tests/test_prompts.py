import unittest

from opsbench.prompts import DEFAULT_SYSTEM_INSTRUCTION, render_prompt
from opsbench.scenarios import EvidenceArtifact, ScenarioManifest, ScenarioPack


class RenderPromptTests(unittest.TestCase):
    def build_pack(self) -> ScenarioPack:
        manifest = ScenarioManifest(
            scenario_id="scenario-001",
            title="Fictional Incident",
            category="kubernetes",
        )
        evidence = (
            EvidenceArtifact(
                artifact_id="pod-logs.txt",
                media_type="text/plain",
                content=b"synthetic error log\n",
            ),
            EvidenceArtifact(
                artifact_id="metrics.json",
                media_type="application/json",
                content=b'{"error_rate": 0.15}\n',
            ),
        )
        return ScenarioPack(manifest, evidence)

    def test_renders_pack_with_default_instruction(self) -> None:
        pack = self.build_pack()

        prompt = render_prompt(pack)

        self.assertIn("# Incident Investigation: scenario-001", prompt)
        self.assertIn("**Category**: kubernetes", prompt)
        self.assertIn("**Title**: Fictional Incident", prompt)
        self.assertIn(DEFAULT_SYSTEM_INSTRUCTION, prompt)
        self.assertIn("### Artifact: pod-logs.txt (text/plain)", prompt)
        self.assertIn("synthetic error log", prompt)
        self.assertIn("### Artifact: metrics.json (application/json)", prompt)
        self.assertIn('"error_rate": 0.15', prompt)
        self.assertIn('"scenario_id": "scenario-001"', prompt)

    def test_renders_pack_with_custom_instruction(self) -> None:
        pack = self.build_pack()

        prompt = render_prompt(
            pack, system_instruction="Custom SRE prompt instruction."
        )

        self.assertIn("Custom SRE prompt instruction.", prompt)
        self.assertNotIn(DEFAULT_SYSTEM_INSTRUCTION, prompt)

    def test_handles_non_utf8_evidence_bytes(self) -> None:
        manifest = ScenarioManifest("scenario-002", "Binary Evidence", "observability")
        evidence = (
            EvidenceArtifact(
                artifact_id="binary.bin",
                media_type="application/octet-stream",
                content=b"valid \xff\xfe invalid\n",
            ),
        )
        pack = ScenarioPack(manifest, evidence)

        prompt = render_prompt(pack)

        self.assertIn("### Artifact: binary.bin (application/octet-stream)", prompt)
        self.assertIn("valid ", prompt)

    def test_rejects_invalid_pack_and_empty_instruction(self) -> None:
        pack = self.build_pack()

        with self.assertRaisesRegex(ValueError, "pack must be a ScenarioPack"):
            render_prompt("not-a-pack")  # type: ignore[arg-type]

        with self.assertRaisesRegex(ValueError, "system_instruction cannot be empty"):
            render_prompt(pack, system_instruction="   ")


if __name__ == "__main__":
    unittest.main()
