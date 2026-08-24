"""Deterministic scoring primitives for OpsBench evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


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