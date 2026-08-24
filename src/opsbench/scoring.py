"""Deterministic scoring primitives for OpsBench evaluations."""

from __future__ import annotations

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