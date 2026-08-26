"""Prompt generation utilities for rendering scenario packs into LLM inputs."""

from __future__ import annotations

from opsbench.scenarios import ScenarioPack

DEFAULT_SYSTEM_INSTRUCTION = (
    "You are an expert site reliability engineer investigating an operational incident."
)


def render_prompt(
    pack: ScenarioPack,
    *,
    system_instruction: str | None = None,
) -> str:
    """Render a scenario pack into a deterministic, structured prompt string."""
    if not isinstance(pack, ScenarioPack):
        raise ValueError("pack must be a ScenarioPack")

    instruction = (system_instruction or DEFAULT_SYSTEM_INSTRUCTION).strip()
    if not instruction:
        raise ValueError("system_instruction cannot be empty")

    sections: list[str] = [
        f"# Incident Investigation: {pack.manifest.scenario_id}",
        f"**Category**: {pack.manifest.category}",
        f"**Title**: {pack.manifest.title}",
        "",
        "## Role & Objective",
        instruction,
        "",
        "## Provided Evidence",
    ]

    for artifact in pack.evidence:
        sections.append(f"### Artifact: {artifact.artifact_id} ({artifact.media_type})")
        sections.append("```")
        try:
            content_text = artifact.content.decode("utf-8")
        except UnicodeDecodeError:
            content_text = artifact.content.decode("utf-8", errors="replace")
        sections.append(content_text.rstrip())
        sections.append("```")
        sections.append("")

    sections.extend(
        [
            "## Required Output Format",
            "Respond ONLY with a valid JSON object matching the following schema:",
            "```json",
            "{",
            f'  "scenario_id": "{pack.manifest.scenario_id}",',
            '  "analysis": "<detailed root-cause explanation>",',
            '  "cited_artifact_ids": ["<artifact_id_1>", "..."],',
            '  "proposed_actions": ["<remediation_action_1>", "..."],',
            '  "model_name": "<your_model_identifier>"',
            "}",
            "```",
        ]
    )

    return "\n".join(sections) + "\n"
