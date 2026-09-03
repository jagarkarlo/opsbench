import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from opsbench.performance import PerformanceMetrics
from opsbench.performance_baseline import (
    PerformanceBaseline,
    PerformanceComparison,
    load_performance_baseline,
    write_performance_baseline,
)


class PerformanceBaselineTests(unittest.TestCase):
    def test_creates_baseline_from_metrics(self) -> None:
        baseline = PerformanceBaseline.from_metrics(
            PerformanceMetrics(name="suite-aggregate", wall_time_seconds=2.0, items_processed=10)
        )

        self.assertEqual(baseline.name, "suite-aggregate")
        self.assertEqual(baseline.wall_time_seconds, 2.0)
        self.assertEqual(baseline.items_processed, 10)
        self.assertTrue(baseline.created_at_utc)

    def test_persists_and_loads_baseline(self) -> None:
        baseline = PerformanceBaseline(
            name="suite-aggregate",
            wall_time_seconds=2.0,
            items_processed=10,
            created_at_utc="2026-09-03T12:00:00+00:00",
        )
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "baseline.json"
            write_performance_baseline(path, baseline)
            loaded = load_performance_baseline(path)

            self.assertEqual(loaded, baseline)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), baseline.to_dict())
            with self.assertRaisesRegex(ValueError, "already exists"):
                write_performance_baseline(path, baseline)

    def test_detects_regression_above_threshold(self) -> None:
        baseline = PerformanceBaseline(
            name="run-scenario-001",
            wall_time_seconds=2.0,
            items_processed=1,
            created_at_utc="2026-09-03T12:00:00+00:00",
        )
        current = PerformanceMetrics(name="run-scenario-001", wall_time_seconds=2.21)
        comparison = PerformanceComparison(baseline, current, threshold_percent=10.0)

        self.assertTrue(comparison.is_regression())
        self.assertAlmostEqual(comparison.wall_time_change_percent(), 10.5)
        self.assertTrue(comparison.to_dict()["is_regression"])

    def test_does_not_flag_measurement_at_threshold(self) -> None:
        baseline = PerformanceBaseline(
            name="run-scenario-001",
            wall_time_seconds=2.0,
            items_processed=1,
            created_at_utc="2026-09-03T12:00:00+00:00",
        )
        current = PerformanceMetrics(name="run-scenario-001", wall_time_seconds=2.2)

        self.assertFalse(PerformanceComparison(baseline, current, 10.0).is_regression())


if __name__ == "__main__":
    unittest.main()
