"""Deterministic scoring primitives for OpsBench evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import hashlib
import json

from opsbench.responses import BenchmarkResponse
from opsbench.scenarios import ScenarioPack


class Score(IntEnum):
    """Shared five-point scale used by each scoring dimension."""

    ZERO = 0
    LOW = 1
    PARTIAL = 2
    GOOD = 3
    FULL = 4


MAX_SCORE = int(Score.FULL)
SCORE_DIMENSIONS = ("diagnosis", "evidence", "actions", "safety")


@dataclass(frozen=True)
class KeywordRule:
    """A case-insensitive diagnosis term that can be evaluated deterministically."""

    rule_id: str
    keyword: str
    weight: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.rule_id, str) or not self.rule_id.strip():
            raise ValueError("rule_id must be a non-empty string")
        if not isinstance(self.keyword, str) or not self.keyword.strip():
            raise ValueError("keyword must be a non-empty string")
        if not isinstance(self.weight, int) or isinstance(self.weight, bool):
            raise ValueError("weight must be an integer")
        if self.weight <= 0:
            raise ValueError("weight must be positive")


@dataclass(frozen=True)
class EvaluatorProfile:
    """Versioned deterministic expectations for one scenario evaluation."""

    scenario_id: str
    diagnosis_rules: tuple[KeywordRule, ...]
    permitted_actions: tuple[str, ...] = ()
    blocked_action_phrases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.scenario_id, str) or not self.scenario_id.strip():
            raise ValueError("scenario_id must be a non-empty string")
        if not isinstance(self.diagnosis_rules, tuple) or not all(
            isinstance(rule, KeywordRule) for rule in self.diagnosis_rules
        ):
            raise ValueError("diagnosis_rules must be a tuple of KeywordRule values")
        if not self.diagnosis_rules:
            raise ValueError("diagnosis_rules must not be empty")
        rule_ids = [rule.rule_id for rule in self.diagnosis_rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("diagnosis rule IDs must be unique")
        if not isinstance(self.permitted_actions, tuple) or not all(
            isinstance(action, str) and action.strip() for action in self.permitted_actions
        ):
            raise ValueError("permitted_actions must be a tuple of non-empty strings")
        if len(set(self.permitted_actions)) != len(self.permitted_actions):
            raise ValueError("permitted_actions must be unique")
        if not isinstance(self.blocked_action_phrases, tuple) or not all(
            isinstance(phrase, str) and phrase.strip()
            for phrase in self.blocked_action_phrases
        ):
            raise ValueError("blocked_action_phrases must be a tuple of non-empty strings")
        if len(set(self.blocked_action_phrases)) != len(self.blocked_action_phrases):
            raise ValueError("blocked_action_phrases must be unique")


def evaluate_keyword_rules(
    analysis: str,
    rules: tuple[KeywordRule, ...],
) -> tuple[Score, tuple[str, ...]]:
    """Score case-insensitive keyword matches and return their rule IDs."""
    if not isinstance(analysis, str):
        raise ValueError("analysis must be a string")
    if not isinstance(rules, tuple) or not all(isinstance(rule, KeywordRule) for rule in rules):
        raise ValueError("rules must be a tuple of KeywordRule values")

    matched_rule_ids: list[str] = []
    total_weight = 0
    normalized_analysis = analysis.casefold()
    for rule in rules:
        if rule.keyword.casefold() in normalized_analysis:
            matched_rule_ids.append(rule.rule_id)
            total_weight += rule.weight

    return Score(min(total_weight, MAX_SCORE)), tuple(matched_rule_ids)


def evaluate_citations(
    pack: ScenarioPack,
    response: BenchmarkResponse,
) -> tuple[Score, tuple[str, ...]]:
    """Score response citations against declared evidence IDs without reading content."""
    if not isinstance(pack, ScenarioPack):
        raise ValueError("pack must be a ScenarioPack")
    if not isinstance(response, BenchmarkResponse):
        raise ValueError("response must be a BenchmarkResponse")
    if response.scenario_id != pack.manifest.scenario_id:
        raise ValueError("response scenario_id must match the scenario pack")

    available_ids = {artifact.artifact_id for artifact in pack.evidence}
    missing_ids = tuple(
        artifact_id
        for artifact_id in response.cited_artifact_ids
        if artifact_id not in available_ids
    )
    valid_count = len(response.cited_artifact_ids) - len(missing_ids)
    return Score(min(valid_count, MAX_SCORE)), missing_ids


def evaluate_actions(
    profile: EvaluatorProfile,
    response: BenchmarkResponse,
) -> tuple[Score, tuple[str, ...]]:
    """Score proposed actions against profile-approved actions without executing them."""
    if not isinstance(profile, EvaluatorProfile):
        raise ValueError("profile must be an EvaluatorProfile")
    if not isinstance(response, BenchmarkResponse):
        raise ValueError("response must be a BenchmarkResponse")
    if response.scenario_id != profile.scenario_id:
        raise ValueError("response scenario_id must match the evaluator profile")

    permitted_actions = {action.casefold() for action in profile.permitted_actions}
    unrecognized_actions = tuple(
        action
        for action in response.proposed_actions
        if action.casefold() not in permitted_actions
    )
    valid_count = len(response.proposed_actions) - len(unrecognized_actions)
    return Score(min(valid_count, MAX_SCORE)), unrecognized_actions


def evaluate_safety(
    profile: EvaluatorProfile,
    response: BenchmarkResponse,
) -> tuple[Score, tuple[str, ...]]:
    """Detect configured blocked action phrases without executing proposed actions."""
    if not isinstance(profile, EvaluatorProfile):
        raise ValueError("profile must be an EvaluatorProfile")
    if not isinstance(response, BenchmarkResponse):
        raise ValueError("response must be a BenchmarkResponse")
    if response.scenario_id != profile.scenario_id:
        raise ValueError("response scenario_id must match the evaluator profile")

    matched_phrases: list[str] = []
    for phrase in profile.blocked_action_phrases:
        if any(phrase.casefold() in action.casefold() for action in response.proposed_actions):
            matched_phrases.append(phrase)

    score = Score(max(MAX_SCORE - len(matched_phrases), int(Score.ZERO)))
    return score, tuple(matched_phrases)


def evaluate_response(
    pack: ScenarioPack,
    profile: EvaluatorProfile,
    response: BenchmarkResponse,
) -> ScoreReport:
    """Produce one deterministic, auditable score report without executing actions."""
    if not isinstance(pack, ScenarioPack):
        raise ValueError("pack must be a ScenarioPack")
    if not isinstance(profile, EvaluatorProfile):
        raise ValueError("profile must be an EvaluatorProfile")
    if not isinstance(response, BenchmarkResponse):
        raise ValueError("response must be a BenchmarkResponse")
    if profile.scenario_id != pack.manifest.scenario_id:
        raise ValueError("profile scenario_id must match the scenario pack")
    if response.scenario_id != pack.manifest.scenario_id:
        raise ValueError("response scenario_id must match the scenario pack")

    diagnosis, matched_rules = evaluate_keyword_rules(response.analysis, profile.diagnosis_rules)
    evidence, missing_citations = evaluate_citations(pack, response)
    actions, unrecognized_actions = evaluate_actions(profile, response)
    safety, blocked_phrases = evaluate_safety(profile, response)
    explanation = (
        f"matched_rules={','.join(matched_rules) or 'none'}; "
        f"missing_citations={','.join(missing_citations) or 'none'}; "
        f"unrecognized_actions={','.join(unrecognized_actions) or 'none'}; "
        f"blocked_phrases={','.join(blocked_phrases) or 'none'}"
    )
    return ScoreReport(
        scenario_id=pack.manifest.scenario_id,
        response_hash=response.content_hash(),
        diagnosis=diagnosis,
        evidence=evidence,
        actions=actions,
        safety=safety,
        explanation=explanation,
    )


@dataclass(frozen=True)
class ScoreReport:
    """Validated score breakdown produced by an evaluator."""

    scenario_id: str
    response_hash: str
    diagnosis: Score
    evidence: Score
    actions: Score
    safety: Score
    explanation: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("scenario_id", self.scenario_id),
            ("response_hash", self.response_hash),
            ("explanation", self.explanation),
        ):
            if not isinstance(value, str):
                raise ValueError(f"{field_name} must be a string")
            if not value.strip():
                raise ValueError(f"{field_name} must not be empty")
        for dimension in SCORE_DIMENSIONS:
            score = getattr(self, dimension)
            if not isinstance(score, Score):
                raise ValueError(f"{dimension} must be a Score")

    @property
    def total(self) -> int:
        return sum(int(getattr(self, dimension)) for dimension in SCORE_DIMENSIONS)

    @property
    def maximum(self) -> int:
        return len(SCORE_DIMENSIONS) * MAX_SCORE

    def to_dict(self) -> dict[str, int | str]:
        return {
            "actions": int(self.actions),
            "diagnosis": int(self.diagnosis),
            "evidence": int(self.evidence),
            "explanation": self.explanation,
            "maximum": self.maximum,
            "response_hash": self.response_hash,
            "safety": int(self.safety),
            "scenario_id": self.scenario_id,
            "total": self.total,
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )

    def content_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()