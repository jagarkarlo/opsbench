"""Command-line entry point for local OpsBench workflows."""

from __future__ import annotations

import argparse


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
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments; command behavior is added in subsequent milestones."""
    build_parser().parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())