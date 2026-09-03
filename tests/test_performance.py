import time
import unittest

from opsbench.performance import PerformanceMetrics, PerformanceProfiler


class PerformanceMetricsTests(unittest.TestCase):
    def test_records_wall_time_and_throughput(self) -> None:
        metrics = PerformanceMetrics(name="test-run", wall_time_seconds=2.0, items_processed=10)

        self.assertEqual(metrics.wall_time_seconds, 2.0)
        self.assertEqual(metrics.throughput_per_second(), 5.0)
        self.assertEqual(metrics.items_processed, 10)

    def test_defaults_to_current_timestamp(self) -> None:
        metrics = PerformanceMetrics(name="test-run", wall_time_seconds=1.0)

        self.assertIsNotNone(metrics.timestamp_utc)
        self.assertTrue(metrics.timestamp_utc.endswith("Z") or "+" in metrics.timestamp_utc)

    def test_rejects_invalid_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "name must be a non-empty string"):
            PerformanceMetrics(name="", wall_time_seconds=1.0)
        with self.assertRaisesRegex(ValueError, "wall_time_seconds must be positive"):
            PerformanceMetrics(name="test", wall_time_seconds=0)
        with self.assertRaisesRegex(ValueError, "items_processed must be positive"):
            PerformanceMetrics(name="test", wall_time_seconds=1.0, items_processed=0)

    def test_serializes_to_dict(self) -> None:
        metrics = PerformanceMetrics(
            name="test-run",
            wall_time_seconds=2.0,
            items_processed=10,
            peak_memory_bytes=1024000,
        )
        d = metrics.to_dict()

        self.assertEqual(d["name"], "test-run")
        self.assertEqual(d["wall_time_seconds"], 2.0)
        self.assertEqual(d["items_processed"], 10)
        self.assertEqual(d["peak_memory_bytes"], 1024000)
        self.assertEqual(d["throughput_per_second"], 5.0)


class PerformanceProfilerTests(unittest.TestCase):
    def test_measures_callable_execution_time(self) -> None:
        profiler = PerformanceProfiler()

        def slow_func() -> int:
            time.sleep(0.01)
            return 42

        result = profiler.measure("sleep-test", slow_func)

        self.assertEqual(result, 42)
        self.assertEqual(len(profiler.recorded_metrics()), 1)
        self.assertGreaterEqual(profiler.recorded_metrics()[0].wall_time_seconds, 0.01)

    def test_tracks_throughput_with_multiple_items(self) -> None:
        profiler = PerformanceProfiler()

        result = profiler.measure(
            "batch-process",
            lambda: 100,
            items_processed=50,
        )

        self.assertEqual(result, 100)
        metrics = profiler.recorded_metrics()[0]
        self.assertEqual(metrics.items_processed, 50)
        self.assertGreater(metrics.throughput_per_second(), 0)

    def test_rejects_invalid_inputs(self) -> None:
        profiler = PerformanceProfiler()

        with self.assertRaisesRegex(ValueError, "name must be a non-empty string"):
            profiler.measure("", lambda: None)

        with self.assertRaisesRegex(TypeError, "func must be callable"):
            profiler.measure("test", "not a function")  # type: ignore

        with self.assertRaisesRegex(ValueError, "items_processed must be positive"):
            profiler.measure("test", lambda: None, items_processed=0)

    def test_clears_recorded_metrics(self) -> None:
        profiler = PerformanceProfiler()
        profiler.measure("test-1", lambda: 1)
        profiler.measure("test-2", lambda: 2)

        self.assertEqual(len(profiler.recorded_metrics()), 2)
        profiler.clear()
        self.assertEqual(len(profiler.recorded_metrics()), 0)


if __name__ == "__main__":
    unittest.main()
