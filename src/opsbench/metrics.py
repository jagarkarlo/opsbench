"""Prometheus-format metrics collector for OpsBench observability."""

from __future__ import annotations

from opsbench.store import RunQuery, SQLiteResultStore


def generate_prometheus_metrics(store: SQLiteResultStore) -> str:
    """Generate Prometheus exposition text format for indexed benchmark store metrics."""
    if not isinstance(store, SQLiteResultStore):
        raise ValueError("store must be a SQLiteResultStore")

    bundles = store.query(RunQuery(limit=10000))
    total_runs = len(bundles)
    scenarios = {bundle.report.scenario_id for bundle in bundles}
    avg_score = (sum(bundle.report.total for bundle in bundles) / total_runs) if total_runs > 0 else 0.0

    lines = [
        "# HELP opsbench_total_runs_indexed Total number of benchmark runs indexed in store.",
        "# TYPE opsbench_total_runs_indexed counter",
        f"opsbench_total_runs_indexed {total_runs}",
        "# HELP opsbench_scenarios_evaluated_count Number of unique scenario packs evaluated.",
        "# TYPE opsbench_scenarios_evaluated_count gauge",
        f"opsbench_scenarios_evaluated_count {len(scenarios)}",
        "# HELP opsbench_average_score Average total score across all indexed runs.",
        "# TYPE opsbench_average_score gauge",
        f"opsbench_average_score {avg_score:.4f}",
    ]
    return "\n".join(lines) + "\n"
