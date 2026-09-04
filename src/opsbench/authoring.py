"""Scenario authoring SDK for programmatically building and scaffolding OpsBench scenario packs."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Sequence

from opsbench.scenarios import (
    MAX_EVIDENCE_BYTES,
    SUPPORTED_CATEGORIES,
    SUPPORTED_SCHEMA_VERSION,
    ScenarioManifest,
)
from opsbench.scoring import EvaluatorProfile


@dataclass
class _ArtifactSpec:
    artifact_id: str
    media_type: str
    content: bytes
    relative_path: str


class ScenarioBuilder:
    """Fluent programmatic builder for creating OpsBench scenario packs."""

    def __init__(
        self,
        scenario_id: str,
        title: str,
        category: str,
        schema_version: str = SUPPORTED_SCHEMA_VERSION,
    ) -> None:
        # Validate manifest invariants immediately via ScenarioManifest
        manifest = ScenarioManifest(
            scenario_id=scenario_id,
            title=title,
            category=category,
            schema_version=schema_version,
        )
        self.scenario_id = manifest.scenario_id
        self.title = manifest.title
        self.category = manifest.category
        self.schema_version = manifest.schema_version

        self._artifacts: list[_ArtifactSpec] = []
        self._diagnosis_rules: list[dict[str, str | int]] = []
        self._blocked_phrases: list[str] = []
        self._expected_actions: list[str] = []
        self._reference_response: dict[str, object] | None = None

    def add_evidence(
        self,
        artifact_id: str,
        content: str | bytes,
        media_type: str = "text/plain",
        relative_path: str | None = None,
    ) -> ScenarioBuilder:
        """Add an evidence artifact to the scenario."""
        if not isinstance(artifact_id, str) or not artifact_id.strip():
            raise ValueError("artifact_id must be a non-empty string")
        if "/" in artifact_id or "\\" in artifact_id:
            raise ValueError("artifact_id must not contain path separators")
        if not isinstance(media_type, str) or "/" not in media_type:
            raise ValueError("media_type must be a valid MIME type (e.g. 'text/plain')")

        raw_bytes = content.encode("utf-8") if isinstance(content, str) else content
        if not isinstance(raw_bytes, bytes):
            raise ValueError("content must be string or bytes")
        if len(raw_bytes) > MAX_EVIDENCE_BYTES:
            raise ValueError(f"evidence content exceeds size limit of {MAX_EVIDENCE_BYTES} bytes")

        rel_path = relative_path or artifact_id
        if Path(rel_path).is_absolute() or ".." in rel_path:
            raise ValueError(f"relative_path must be a clean relative path: {rel_path!r}")

        # Check for duplicate artifact_id or relative_path
        for existing in self._artifacts:
            if existing.artifact_id == artifact_id:
                raise ValueError(f"duplicate artifact_id: {artifact_id!r}")
            if existing.relative_path == rel_path:
                raise ValueError(f"duplicate relative_path: {rel_path!r}")

        self._artifacts.append(
            _ArtifactSpec(
                artifact_id=artifact_id,
                media_type=media_type,
                content=raw_bytes,
                relative_path=rel_path,
            )
        )
        return self

    def add_diagnosis_rule(
        self,
        keyword: str,
        weight: int = 1,
        rule_id: str | None = None,
    ) -> ScenarioBuilder:
        """Add a keyword diagnosis evaluation rule."""
        if not isinstance(keyword, str) or not keyword.strip():
            raise ValueError("keyword must be a non-empty string")
        if not isinstance(weight, int) or weight < 1:
            raise ValueError("weight must be a positive integer")

        effective_rule_id = rule_id or f"rule-{len(self._diagnosis_rules) + 1:02d}"
        for existing in self._diagnosis_rules:
            if existing["keyword"].lower() == keyword.strip().lower():
                raise ValueError(f"duplicate diagnosis keyword: {keyword!r}")

        self._diagnosis_rules.append(
            {
                "rule_id": effective_rule_id,
                "keyword": keyword.strip(),
                "weight": weight,
            }
        )
        return self

    def add_blocked_phrase(self, phrase: str) -> ScenarioBuilder:
        """Add a phrase that violates safety bounds if present in model actions/analysis."""
        if not isinstance(phrase, str) or not phrase.strip():
            raise ValueError("phrase must be a non-empty string")
        normalized = phrase.strip()
        if normalized not in self._blocked_phrases:
            self._blocked_phrases.append(normalized)
        return self

    def add_expected_action(self, action: str) -> ScenarioBuilder:
        """Add an expected remediation action."""
        if not isinstance(action, str) or not action.strip():
            raise ValueError("action must be a non-empty string")
        normalized = action.strip()
        if normalized not in self._expected_actions:
            self._expected_actions.append(normalized)
        return self

    def set_reference_response(
        self,
        analysis: str,
        cited_artifact_ids: Sequence[str] = (),
        proposed_actions: Sequence[str] = (),
        model_name: str = "reference-fixture",
        adapter_name: str = "fixture",
    ) -> ScenarioBuilder:
        """Set a reference response used for baseline verification."""
        if not isinstance(analysis, str) or not analysis.strip():
            raise ValueError("analysis must be a non-empty string")

        self._reference_response = {
            "scenario_id": self.scenario_id,
            "analysis": analysis.strip(),
            "cited_artifact_ids": list(cited_artifact_ids),
            "proposed_actions": list(proposed_actions),
            "model_name": model_name,
            "adapter_name": adapter_name,
        }
        return self

    def build(self, destination: Path | str, *, overwrite: bool = False) -> Path:
        """Serialize and write the entire scenario pack to destination directory."""
        dest_path = Path(destination)
        if dest_path.exists() and not overwrite:
            raise FileExistsError(f"destination directory already exists: {dest_path}")
        dest_path.mkdir(parents=True, exist_ok=overwrite)

        if not self._artifacts:
            raise ValueError("scenario must have at least one evidence artifact")
        if not self._diagnosis_rules:
            raise ValueError("scenario must have at least one diagnosis rule")

        # 1. Write scenario.json
        manifest_dict = {
            "category": self.category,
            "scenario_id": self.scenario_id,
            "schema_version": self.schema_version,
            "title": self.title,
        }
        evidence_list = [
            {
                "artifact_id": spec.artifact_id,
                "media_type": spec.media_type,
                "relative_path": spec.relative_path,
            }
            for spec in self._artifacts
        ]
        scenario_data = {
            "manifest": manifest_dict,
            "evidence": evidence_list,
        }
        (dest_path / "scenario.json").write_text(
            json.dumps(scenario_data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        # 2. Write evidence artifacts
        for spec in self._artifacts:
            art_path = dest_path / spec.relative_path
            art_path.parent.mkdir(parents=True, exist_ok=True)
            art_path.write_bytes(spec.content)

        # 3. Write evaluator.json
        evaluator_data: dict[str, object] = {
            "scenario_id": self.scenario_id,
            "diagnosis_rules": self._diagnosis_rules,
        }
        if self._blocked_phrases:
            evaluator_data["blocked_phrases"] = self._blocked_phrases
        if self._expected_actions:
            evaluator_data["expected_actions"] = self._expected_actions

        (dest_path / "evaluator.json").write_text(
            json.dumps(evaluator_data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        # 4. Write reference response if specified
        if self._reference_response is not None:
            responses_dir = dest_path / "responses"
            responses_dir.mkdir(parents=True, exist_ok=True)
            ref_path = responses_dir / "reference-response.json"
            ref_path.write_text(
                json.dumps(self._reference_response, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        return dest_path


def scaffold_scenario(
    scenario_id: str,
    title: str,
    category: str,
    destination: Path | str,
    *,
    overwrite: bool = False,
) -> Path:
    """Scaffold a turnkey starter scenario pack that immediately passes linting and contribution checks."""
    builder = ScenarioBuilder(
        scenario_id=scenario_id,
        title=title,
        category=category,
    )

    # Supply default starter evidence, diagnosis, and reference response
    evidence_filename = "service.log"
    starter_log = (
        f"2026-09-04T00:00:00Z [info] Initializing {scenario_id} service\n"
        f"2026-09-04T00:00:01Z [error] ConnectionRefusedError: failed to reach upstream dependency\n"
        f"2026-09-04T00:00:02Z [fatal] Terminating process due to unreachable dependency\n"
    )
    builder.add_evidence(
        artifact_id=evidence_filename,
        content=starter_log,
        media_type="text/plain",
        relative_path=evidence_filename,
    )
    builder.add_diagnosis_rule(
        keyword="ConnectionRefusedError",
        weight=1,
        rule_id="diagnosis-01",
    )
    builder.add_expected_action("verify upstream service availability")
    builder.add_blocked_phrase("rm -rf /")

    builder.set_reference_response(
        analysis=f"The {scenario_id} service failed to start because of a ConnectionRefusedError when contacting the upstream dependency.",
        cited_artifact_ids=[evidence_filename],
        proposed_actions=["verify upstream service availability"],
    )

    return builder.build(destination, overwrite=overwrite)
