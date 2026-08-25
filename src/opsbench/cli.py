"""Command-line entry point for local OpsBench workflows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from opsbench.responses import load_response
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

    response_parser = subparsers.add_parser("response", help="evaluate local benchmark responses")
    response_subparsers = response_parser.add_subparsers(dest="response_command", required=True)
    evaluate_parser = response_subparsers.add_parser(
        "evaluate", help="evaluate one response against a local scenario"
    )
    evaluate_parser.add_argument("scenario_path")
    evaluate_parser.add_argument("response_path")
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
                            "scenario_id": scenario.manifest.scenario_id,
                            "title": scenario.manifest.title,
                        }
                        for scenario in gallery.scenarios
                    ],
                },
                sort_keys=True,
            )
        )
    if parsed.command == "response" and parsed.response_command == "evaluate":
        scenario_path = Path(parsed.scenario_path)
        pack = load_scenario_pack(scenario_path)
        profile = load_evaluator_profile(scenario_path / "evaluator.json")
        response = load_response(Path(parsed.response_path))
        report = evaluate_response(pack, profile, response)
        print(json.dumps(report.to_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())