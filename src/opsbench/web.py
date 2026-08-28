"""Zero-dependency HTML dashboard rendering for OpsBench web console."""

from __future__ import annotations

import html
from opsbench.comparisons import summarize_trials
from opsbench.store import SQLiteResultStore, RunQuery


def render_dashboard_html(store: SQLiteResultStore) -> str:
    """Render a standalone HTML dashboard page summarizing indexed benchmark results."""
    if not isinstance(store, SQLiteResultStore):
        raise ValueError("store must be a SQLiteResultStore")

    bundles = store.query(RunQuery(limit=500))
    total_runs = len(bundles)
    scenario_ids = {bundle.report.scenario_id for bundle in bundles}

    if total_runs > 0:
        avg_score = sum(bundle.report.total for bundle in bundles) / total_runs
        avg_score_str = f"{avg_score:.2f}"
    else:
        avg_score_str = "N/A"

    # Group by scenario for leaderboard summaries
    scenarios_data: dict[str, list] = {}
    for bundle in bundles:
        scenarios_data.setdefault(bundle.report.scenario_id, []).append(bundle)

    leaderboard_rows: list[str] = []
    for scenario_id in sorted(scenarios_data.keys()):
        scenario_bundles = tuple(scenarios_data[scenario_id])
        trials = summarize_trials(scenario_bundles)
        for stat in trials:
            leaderboard_rows.append(
                f"<tr>"
                f"<td><code>{html.escape(scenario_id)}</code></td>"
                f"<td><strong>{html.escape(stat.runner_name)}</strong></td>"
                f"<td>{stat.trial_count}</td>"
                f"<td>{stat.total_score}</td>"
                f"<td>{stat.average_score:.2f}</td>"
                f"</tr>"
            )

    recent_runs_rows: list[str] = []
    for bundle in bundles[:20]:
        runner_label = bundle.run.model_name or bundle.run.runner_kind
        recent_runs_rows.append(
            f"<tr>"
            f"<td><code>{html.escape(bundle.run.run_id)}</code></td>"
            f"<td><code>{html.escape(bundle.report.scenario_id)}</code></td>"
            f"<td>{html.escape(runner_label)}</td>"
            f"<td><strong>{bundle.report.total}</strong> / {bundle.report.maximum}</td>"
            f"<td>{html.escape(bundle.run.started_at)}</td>"
            f"</tr>"
        )

    leaderboard_html = (
        "\n".join(leaderboard_rows)
        if leaderboard_rows
        else "<tr><td colspan='5'>No benchmark runs recorded yet.</td></tr>"
    )
    recent_html = (
        "\n".join(recent_runs_rows)
        if recent_runs_rows
        else "<tr><td colspan='5'>No recent runs found.</td></tr>"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpsBench Console</title>
    <style>
        :root {{
            --bg: #0f172a;
            --card-bg: #1e293b;
            --text: #f8fafc;
            --muted: #94a3b8;
            --primary: #38bdf8;
            --border: #334155;
            --accent: #22c55e;
        }}
        body {{
            font-family: system-ui, -apple-system, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 2rem;
        }}
        .container {{
            max-width: 1100px;
            margin: 0 auto;
        }}
        h1 {{
            color: var(--primary);
            margin-bottom: 0.5rem;
        }}
        .subtitle {{
            color: var(--muted);
            margin-bottom: 2rem;
        }}
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.25rem;
        }}
        .metric-value {{
            font-size: 2rem;
            font-weight: bold;
            color: var(--primary);
        }}
        .metric-label {{
            color: var(--muted);
            font-size: 0.875rem;
            text-transform: uppercase;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background-color: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            overflow: hidden;
            margin-bottom: 2rem;
        }}
        th, td {{
            padding: 0.75rem 1rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        th {{
            background-color: #1e293b;
            color: var(--muted);
            font-size: 0.85rem;
            text-transform: uppercase;
        }}
        code {{
            background-color: #0f172a;
            padding: 0.2rem 0.4rem;
            border-radius: 4px;
            color: var(--primary);
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>OpsBench Web Console</h1>
        <div class="subtitle">
            Open Benchmark Platform for AI Incident Diagnosis &middot;
            <a href="/pipeline" style="color: var(--primary);">View 3D Pipeline</a>
        </div>

        <div class="metrics">
            <div class="card">
                <div class="metric-value">{total_runs}</div>
                <div class="metric-label">Total Indexed Runs</div>
            </div>
            <div class="card">
                <div class="metric-value">{len(scenario_ids)}</div>
                <div class="metric-label">Scenarios Evaluated</div>
            </div>
            <div class="card">
                <div class="metric-value">{avg_score_str}</div>
                <div class="metric-label">Average Score</div>
            </div>
        </div>

        <h2>Leaderboard Summaries</h2>
        <table>
            <thead>
                <tr>
                    <th>Scenario ID</th>
                    <th>Runner / Model</th>
                    <th>Trials</th>
                    <th>Total Score</th>
                    <th>Avg Score</th>
                </tr>
            </thead>
            <tbody>
                {leaderboard_html}
            </tbody>
        </table>

        <h2>Recent Runs</h2>
        <table>
            <thead>
                <tr>
                    <th>Run ID</th>
                    <th>Scenario ID</th>
                    <th>Runner / Model</th>
                    <th>Score</th>
                    <th>Started At</th>
                </tr>
            </thead>
            <tbody>
                {recent_html}
            </tbody>
        </table>
    </div>
</body>
</html>
"""
