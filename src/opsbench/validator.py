"""Scenario linting and strict validation engine for OpsBench scenario packs."""

from __future__ import annotations

import json
from pathlib import Path

from opsbench.scenarios import (
    MANIFEST_FIELDS,
    MAX_EVIDENCE_BYTES,
    MAX_MANIFEST_BYTES,
    SUPPORTED_CATEGORIES,
    SUPPORTED_SCHEMA_VERSION,
)
from opsbench.scoring import MAX_PROFILE_BYTES, PROFILE_FIELDS


def lint_scenario(scenario_directory: Path) -> list[str]:
    """Perform static linting on a scenario directory and return a list of issue descriptions."""
    issues: list[str] = []

    if not isinstance(scenario_directory, Path) or not scenario_directory.is_dir():
        return [f"path is not a directory: {scenario_directory}"]

    manifest_path = scenario_directory / "scenario.json"
    if not manifest_path.is_file():
        issues.append(f"missing scenario.json in {scenario_directory}")
        return issues

    if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
        issues.append(f"scenario.json exceeds maximum size of {MAX_MANIFEST_BYTES} bytes")
        return issues

    try:
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        issues.append(f"scenario.json is invalid JSON: {error}")
        return issues

    if not isinstance(manifest_data, dict):
        issues.append("scenario.json root must be a JSON object")
        return issues

    manifest = manifest_data.get("manifest")
    if not isinstance(manifest, dict):
        issues.append("scenario.json missing manifest object")
    else:
        schema_version = manifest.get("schema_version")
        if schema_version != SUPPORTED_SCHEMA_VERSION:
            issues.append(f"unsupported schema_version: {schema_version!r}")
        category = manifest.get("category")
        if category not in SUPPORTED_CATEGORIES:
            issues.append(f"unknown scenario category: {category!r}")
        scenario_id = manifest.get("scenario_id")
        if not isinstance(scenario_id, str) or not scenario_id.strip():
            issues.append("manifest scenario_id must be a non-empty string")

    evidence = manifest_data.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        issues.append("scenario.json evidence must be a non-empty list of artifact references")
    else:
        for idx, ref in enumerate(evidence):
            if not isinstance(ref, dict):
                issues.append(f"evidence[{idx}] must be an object")
                continue
            rel_path = ref.get("relative_path")
            if isinstance(rel_path, str):
                artifact_file = scenario_directory / rel_path
                if not artifact_file.is_file():
                    issues.append(f"declared evidence file does not exist: {rel_path}")
                elif artifact_file.stat().st_size > MAX_EVIDENCE_BYTES:
                    issues.append(f"evidence file {rel_path} exceeds size limit of {MAX_EVIDENCE_BYTES} bytes")

    evaluator_path = scenario_directory / "evaluator.json"
    if not evaluator_path.is_file():
        issues.append(f"missing evaluator.json in {scenario_directory}")
    else:
        if evaluator_path.stat().st_size > MAX_PROFILE_BYTES:
            issues.append("evaluator.json exceeds maximum size limit")
        else:
            try:
                eval_data = json.loads(evaluator_path.read_text(encoding="utf-8"))
                if not isinstance(eval_data, dict):
                    issues.append("evaluator.json root must be a JSON object")
                else:
                    rules = eval_data.get("diagnosis_rules")
                    if not isinstance(rules, list) or not rules:
                        issues.append("evaluator.json diagnosis_rules must be a non-empty list")
                    else:
                        keywords = set()
                        for r_idx, rule in enumerate(rules):
                            if isinstance(rule, dict):
                                kw = rule.get("keyword")
                                if isinstance(kw, str):
                                    kw_lower = kw.lower()
                                    if kw_lower in keywords:
                                        issues.append(f"duplicate diagnosis rule keyword: {kw!r}")
                                    keywords.add(kw_lower)
            except json.JSONDecodeError as error:
                issues.append(f"evaluator.json is invalid JSON: {error}")

    return issues
