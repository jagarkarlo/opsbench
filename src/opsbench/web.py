"""Zero-dependency HTML dashboard rendering for OpsBench web console."""

from __future__ import annotations

import html
from opsbench.comparisons import rank_portfolio, summarize_trials
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

    portfolio_rows: list[str] = []
    if bundles:
        for rank, statistic in enumerate(rank_portfolio(tuple(bundles)), start=1):
            interval = statistic.confidence_interval_95
            portfolio_rows.append(
                f"<tr>"
                f"<td>{rank}</td>"
                f"<td><strong>{html.escape(statistic.runner_name)}</strong></td>"
                f"<td>{statistic.scenario_count}</td>"
                f"<td>{statistic.trial_count}</td>"
                f"<td>{statistic.average_score:.3f}</td>"
                f"<td>{statistic.conservative_score:.3f}</td>"
                f"<td>[{interval[0]:.3f}, {interval[1]:.3f}]</td>"
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
    portfolio_html = (
        "\n".join(portfolio_rows)
        if portfolio_rows
        else "<tr><td colspan='7'>No portfolio results recorded yet.</td></tr>"
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
        /* A printed operator's log, not another dark SaaS dashboard. */
        :root {{
            --paper: #f3efe6;
            --ink: #26221c;
            --faint: #7a7364;
            --rule: #c9c0ac;
            --rust: #a6491f;
            --moss: #4c6b47;
        }}
        body {{
            font-family: Georgia, "Iowan Old Style", serif;
            background-color: var(--paper);
            color: var(--ink);
            margin: 0;
            padding: 2.5rem 1.5rem;
        }}
        .container {{
            max-width: 1100px;
            margin: 0 auto;
        }}
        h1 {{
            color: var(--ink);
            margin: 0 0 .15rem;
            font-weight: normal;
            letter-spacing: .02em;
        }}
        .subtitle {{
            color: var(--faint);
            font-style: italic;
            margin-bottom: 2.25rem;
            padding-bottom: 1.25rem;
            border-bottom: 2px solid var(--ink);
        }}
        .stat-line {{
            display: flex;
            flex-wrap: wrap;
            gap: .35rem 0;
            margin-bottom: 2.5rem;
            font-size: 1.05rem;
        }}
        .stat-line span {{
            padding: 0 1.1rem;
            border-right: 1px solid var(--rule);
        }}
        .stat-line span:first-child {{ padding-left: 0; }}
        .stat-line span:last-child {{ border-right: none; }}
        .stat-line strong {{
            color: var(--rust);
            font-size: 1.4rem;
            font-weight: normal;
        }}
        .stat-line small {{
            display: block;
            color: var(--faint);
            font-size: .7rem;
            letter-spacing: .08em;
            text-transform: uppercase;
            font-style: normal;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 2.75rem;
        }}
        th, td {{
            padding: .55rem .9rem;
            text-align: left;
            border-bottom: 1px solid var(--rule);
        }}
        td:first-child, th:first-child {{ padding-left: 0; }}
        tbody tr:nth-child(odd) {{ background-color: rgba(166, 73, 31, .05); }}
        th {{
            font-size: .72rem;
            letter-spacing: .09em;
            text-transform: uppercase;
            color: var(--faint);
            font-weight: normal;
            border-bottom: 2px solid var(--ink);
        }}
        code {{
            font-family: ui-monospace, "SF Mono", Menlo, monospace;
            color: var(--moss);
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>OpsBench Web Console</h1>
        <div class="subtitle">
            Open Benchmark Platform for AI Incident Diagnosis
        </div>

        <div class="stat-line">
            <span><strong>{total_runs}</strong><small>Total Indexed Runs</small></span>
            <span><strong>{len(scenario_ids)}</strong><small>Scenarios Evaluated</small></span>
            <span><strong>{avg_score_str}</strong><small>Average Score</small></span>
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

        <h2>Portfolio Leaderboard</h2>
        <p>Normalized across scenarios so different scoring scales can be compared.</p>
        <table>
            <thead>
                <tr>
                    <th>Rank</th>
                    <th>Runner / Model</th>
                    <th>Scenarios</th>
                    <th>Trials</th>
                    <th>Average</th>
                    <th>Conservative Score</th>
                    <th>95% CI</th>
                </tr>
            </thead>
            <tbody>
                {portfolio_html}
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
