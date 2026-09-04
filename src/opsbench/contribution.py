"""Strict contribution and readiness checks for OpsBench scenario packs."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Sequence

from opsbench.responses import load_response
from opsbench.scenarios import (
    SUPPORTED_CATEGORIES,
    ScenarioPack,
    load_scenario_pack,
)
from opsbench.scoring import (
    EvaluatorProfile,
    Score,
    evaluate_response,
    load_evaluator_profile,
)
from opsbench.validator import lint_scenario

# Patterns indicating potential credential or secret leakage in contributed scenarios
_FORBIDDEN_SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"), "private key header"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key ID"),
    (re.compile(r"\bghp_[a-zA-Z0-9]{36}\b"), "GitHub personal access token"),
    (re.compile(r"\bgithub_pat_[a-zA-Z0-9_]{30,}\b"), "fine-grained GitHub personal access token"),
    (re.compile(r"\bxox[baprs]-[0-9a-zA-Z]{10,}\b"), "Slack API token"),
]

_SCENARIO_ID_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MINIMUM_EVIDENCE_BYTES = 10
MINIMUM_KEYWORD_LENGTH = 3


@dataclass(frozen=True)
class ContributionCheckResult:
    """Outcome of running strict contribution readiness checks on one scenario."""

    scenario_id: str
    path: str
    passed: bool
    checks_run: tuple[str, ...]
    issues: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "checks_run": list(self.checks_run),
            "issues": list(self.issues),
            "passed": self.passed,
            "path": self.path,
            "scenario_id": self.scenario_id,
            "warnings": list(self.warnings),
        }


def check_contribution(scenario_directory: Path | str) -> ContributionCheckResult:
    """Run all strict contribution verification checks on a candidate scenario directory."""
    dir_path = Path(scenario_directory)
    checks: list[str] = []
    issues: list[str] = []
    warnings: list[str] = []

    scenario_id_found = dir_path.name

    # 1. Static linting
    checks.append("lint")
    lint_issues = lint_scenario(dir_path)
    if lint_issues:
        issues.extend([f"lint: {msg}" for msg in lint_issues])
        return ContributionCheckResult(
            scenario_id=scenario_id_found,
            path=str(dir_path),
            passed=False,
            checks_run=tuple(checks),
            issues=tuple(issues),
            warnings=tuple(warnings),
        )

    # 2. Pack and Profile loading
    checks.append("load_pack_and_profile")
    pack: ScenarioPack | None = None
    profile: EvaluatorProfile | None = None
    try:
        pack = load_scenario_pack(dir_path)
        scenario_id_found = pack.manifest.scenario_id
        profile = load_evaluator_profile(dir_path / "evaluator.json")
    except Exception as exc:
        issues.append(f"failed to load scenario pack or evaluator: {exc}")
        return ContributionCheckResult(
            scenario_id=scenario_id_found,
            path=str(dir_path),
            passed=False,
            checks_run=tuple(checks),
            issues=tuple(issues),
            warnings=tuple(warnings),
        )

    # 3. ID and Naming conventions
    checks.append("naming_convention")
    if not _SCENARIO_ID_PATTERN.match(pack.manifest.scenario_id):
        issues.append(
            f"scenario_id {pack.manifest.scenario_id!r} does not match recommended lower-case "
            f"alphanumeric with hyphens pattern '^[a-z0-9]+(-[a-z0-9]+)*$'"
        )
    if not pack.manifest.scenario_id.startswith(pack.manifest.category):
        warnings.append(
            f"scenario_id {pack.manifest.scenario_id!r} does not begin with its category {pack.manifest.category!r}"
        )

    # 4. Evidence depth and content integrity
    checks.append("evidence_depth")
    if not pack.evidence:
        issues.append("scenario does not declare any evidence artifacts")
    for artifact in pack.evidence:
        if len(artifact.content) < MINIMUM_EVIDENCE_BYTES:
            issues.append(
                f"evidence artifact {artifact.artifact_id!r} content is too short "
                f"({len(artifact.content)} bytes, minimum {MINIMUM_EVIDENCE_BYTES} bytes)"
            )

    # 5. Evaluator rule quality
    checks.append("evaluator_rules")
    total_weight = sum(rule.weight for rule in profile.diagnosis_rules)
    if total_weight < 1:
        issues.append("evaluator diagnosis rules must have positive total weight")
    for rule in profile.diagnosis_rules:
        if len(rule.keyword) < MINIMUM_KEYWORD_LENGTH:
            issues.append(
                f"diagnosis rule {rule.rule_id!r} keyword {rule.keyword!r} is too short "
                f"(length {len(rule.keyword)}, minimum {MINIMUM_KEYWORD_LENGTH})"
            )

    # 6. Reference response presence and viability
    checks.append("reference_response_viability")
    responses_dir = dir_path / "responses"
    if not responses_dir.is_dir():
        issues.append("missing responses/ directory containing reference response")
    else:
        response_files = [p for p in responses_dir.glob("*.json") if p.is_file()]
        if not response_files:
            issues.append("responses/ directory contains no JSON response files")
        else:
            evaluated_at_least_one_passing = False
            for resp_file in response_files:
                try:
                    ref_resp = load_response(resp_file)
                    report = evaluate_response(pack, profile, ref_resp)
                    if int(report.diagnosis) > 0 and int(report.safety) > 0:
                        evaluated_at_least_one_passing = True
                    else:
                        warnings.append(
                            f"reference response {resp_file.name} scored diagnosis={report.diagnosis} "
                            f"safety={report.safety}"
                        )
                except Exception as resp_exc:
                    issues.append(f"failed to load and evaluate reference response {resp_file.name}: {resp_exc}")

            if response_files and not evaluated_at_least_one_passing and not issues:
                issues.append("no reference response achieved a passing diagnosis score against evaluator rules")

    # 7. Credential hygiene and secret scan
    checks.append("safety_hygiene")
    files_to_scan: list[Path] = [
        dir_path / "scenario.json",
        dir_path / "evaluator.json",
    ]
    for art in pack.evidence:
        files_to_scan.append(dir_path / art.artifact_id)
    if responses_dir.is_dir():
        files_to_scan.extend(responses_dir.glob("*.json"))

    for scan_file in files_to_scan:
        if scan_file.is_file():
            try:
                text_content = scan_file.read_text(encoding="utf-8", errors="replace")
                for pattern, desc in _FORBIDDEN_SECRET_PATTERNS:
                    if pattern.search(text_content):
                        issues.append(f"prohibited secret leak detected in {scan_file.name}: {desc}")
            except Exception:
                pass

    passed = len(issues) == 0
    return ContributionCheckResult(
        scenario_id=scenario_id_found,
        path=str(dir_path),
        passed=passed,
        checks_run=tuple(checks),
        issues=tuple(issues),
        warnings=tuple(warnings),
    )


def check_gallery_contributions(gallery_directory: Path | str) -> list[ContributionCheckResult]:
    """Run contribution checks across all scenarios in a gallery directory."""
    gallery_path = Path(gallery_directory)
    if not gallery_path.is_dir():
        raise NotADirectoryError(f"gallery path is not a directory: {gallery_path}")

    results: list[ContributionCheckResult] = []
    for candidate in sorted(gallery_path.iterdir()):
        if candidate.is_dir() and (candidate / "scenario.json").is_file():
            results.append(check_contribution(candidate))
    return results
