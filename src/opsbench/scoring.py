"""Deterministic scoring primitives for OpsBench evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import hashlib
import json


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