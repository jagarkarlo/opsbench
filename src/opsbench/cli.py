"""Command-line entry point for local OpsBench workflows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from opsbench.adapters import FixtureResponseAdapter, HumanResponseAdapter
from opsbench.comparisons import (
    compare_bundles,
    render_markdown_comparison,
    summarize_trials,
)
from opsbench.prompts import render_prompt
from opsbench.responses import load_response
from opsbench.runner import execute_run
from opsbench.runs import ResultBundle, load_result_bundle, write_result_bundle
from opsbench.scenarios import load_gallery, load_scenario_pack
from opsbench.scoring import evaluate_response, load_evaluator_profile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="opsbench")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scenario_parser = subparsers.add_parser("scenario", help="inspect local scenarios")
    scenario_subparsers = scenario_parser.add_subparsers(dest="scenario_command", required=True)
    validate_parser = scenario_subparsers.add_parser(
        "validate", help="validate one scenario directory"
    )
    validate_parser.add_argument("path")

    list_parser = scenario_subparsers.add_parser("list", help="list a local scenario gallery")
    list_parser.add_argument("path")

    audit_parser = scenario_subparsers.add_parser(
        "audit", help="validate every scenario in a local gallery"
    )
    audit_parser.add_argument("path")
    prompt_parser = scenario_subparsers.add_parser(
        "prompt", help="render a reproducible LLM prompt from a scenario pack"
    )
    prompt_parser.add_argument("path")
    prompt_parser.add_argument("--instruction", help="custom system instruction")
    response_parser = subparsers.add_parser("response", help="evaluate local benchmark responses")
    response_subparsers = response_parser.add_subparsers(dest="response_command", required=True)
    evaluate_parser = response_subparsers.add_parser(
        "evaluate", help="evaluate one response against a local scenario"
    )
    evaluate_parser.add_argument("scenario_path")
    evaluate_parser.add_argument("response_path")

    run_parser = subparsers.add_parser("run", help="execute local benchmark runs")
    run_subparsers = run_parser.add_subparsers(dest="run_command", required=True)
    fixture_parser = run_subparsers.add_parser(
        "fixture", help="execute one deterministic fixture response"
    )
    fixture_parser.add_argument("scenario_path")
    fixture_parser.add_argument("response_path")
    fixture_parser.add_argument("output_path")
    fixture_parser.add_argument("--run-id", required=True)
    human_parser = run_subparsers.add_parser(
        "human", help="execute one locally supplied human response"
    )
    human_parser.add_argument("scenario_path")
    human_parser.add_argument("response_path")
    human_parser.add_argument("output_path")
    human_parser.add_argument("--run-id", required=True)

    compare_parser = subparsers.add_parser("compare", help="compare local benchmark results")
    compare_subparsers = compare_parser.add_subparsers(dest="compare_command", required=True)
    results_parser = compare_subparsers.add_parser(
        "results", help="summarize immutable result bundle files"
    )
    results_parser.add_argument("bundle_paths", nargs="+")
    results_parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="output format (default: json)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Execute one local scenario command."""
    parsed = build_parser().parse_args(argv)
    if parsed.command == "scenario" and parsed.scenario_command == "validate":
        pack = load_scenario_pack(Path(parsed.path))
        print(
            json.dumps(
                {
                    "category": pack.manifest.category,
                    "evidence_count": len(pack.evidence),
                    "pack_hash": pack.content_hash(),
                    "scenario_id": pack.manifest.scenario_id,
                    "valid": True,
                },
                sort_keys=True,
            )
        )
    if parsed.command == "scenario" and parsed.scenario_command == "list":
        gallery = load_gallery(Path(parsed.path))
        print(
            json.dumps(
                {
                    "scenario_count": len(gallery.scenarios),
                    "scenarios": [
                        {
                            "category": scenario.manifest.category,
                            "pack_hash": scenario.content_hash(),
                            "scenario_id": scenario.manifest.scenario_id,
                            "title": scenario.manifest.title,
                        }
                        for scenario in gallery.scenarios
                    ],
                },
                sort_keys=True,
            )
        )
    if parsed.command == "scenario" and parsed.scenario_command == "audit":
        gallery = load_gallery(Path(parsed.path))
        print(
            json.dumps(
                {
                    "audit_passed": True,
                    "scenario_count": len(gallery.scenarios),
                    "scenarios": [
                        {
                            "category": scenario.manifest.category,
                            "pack_hash": scenario.content_hash(),
                            "scenario_id": scenario.manifest.scenario_id,
                        }
                        for scenario in gallery.scenarios
                    ],
                },
                sort_keys=True,
            )
        )
    if parsed.command == "scenario" and parsed.scenario_command == "prompt":
        pack = load_scenario_pack(Path(parsed.path))
        prompt_text = render_prompt(
            pack,
            system_instruction=parsed.instruction,
        )
        print(prompt_text, end="")
    if parsed.command == "response" and parsed.response_command == "evaluate":
        scenario_path = Path(parsed.scenario_path)
        pack = load_scenario_pack(scenario_path)
        profile = load_evaluator_profile(scenario_path / "evaluator.json")
        response = load_response(Path(parsed.response_path))
        report = evaluate_response(pack, profile, response)
        print(json.dumps(report.to_dict(), sort_keys=True))
    if parsed.command == "run" and parsed.run_command in {"fixture", "human"}:
        scenario_path = Path(parsed.scenario_path)
        pack = load_scenario_pack(scenario_path)
        profile = load_evaluator_profile(scenario_path / "evaluator.json")
        response = load_response(Path(parsed.response_path))
        adapter = (
            FixtureResponseAdapter(response)
            if parsed.run_command == "fixture"
            else HumanResponseAdapter(response)
        )
        result = execute_run(
            run_id=parsed.run_id,
            pack=pack,
            profile=profile,
            adapter=adapter,
        )
        bundle = ResultBundle(result.run, result.report)
        output_path = Path(parsed.output_path)
        write_result_bundle(output_path, bundle)
        print(
            json.dumps(
                {
                    "bundle_hash": bundle.content_hash(),
                    "output_path": str(output_path),
                    "report": result.report.to_dict(),
                    "run": result.run.to_dict(),
                },
                sort_keys=True,
            )
        )
    if parsed.command == "compare" and parsed.compare_command == "results":
        bundles = tuple(load_result_bundle(Path(path)) for path in parsed.bundle_paths)
        if parsed.format == "markdown":
            print(render_markdown_comparison(bundles), end="")
        else:
            summary = compare_bundles(bundles)
            trials = summarize_trials(bundles)
            print(
                json.dumps(
                    {
                        "runner_totals": [
                            {"runner_name": name, "total_score": total}
                            for name, total in summary.runner_totals
                        ],
                        "scenario_id": summary.scenario_id,
                        "trials": [
                            {
                                "average_score": statistic.average_score,
                                "runner_name": statistic.runner_name,
                                "total_score": statistic.total_score,
                                "trial_count": statistic.trial_count,
                            }
                            for statistic in trials
                        ],
                    },
                    sort_keys=True,
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())