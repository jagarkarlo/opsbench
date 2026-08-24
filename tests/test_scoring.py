import unittest

from opsbench.scoring import MAX_SCORE, SCORE_DIMENSIONS, Score


class ScoreTests(unittest.TestCase):
    def test_score_scale_is_bounded_and_ordered(self) -> None:
        self.assertEqual(int(Score.ZERO), 0)
        self.assertEqual(int(Score.FULL), MAX_SCORE)
        self.assertLess(Score.PARTIAL, Score.GOOD)

    def test_dimensions_are_explicit_and_stable(self) -> None:
        self.assertEqual(
            SCORE_DIMENSIONS,
            ("diagnosis", "evidence", "actions", "safety"),
        )