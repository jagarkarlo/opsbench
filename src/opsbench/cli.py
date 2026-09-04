"""Command-line entry point for local OpsBench workflows."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from opsbench.adapters import (
    FixtureResponseAdapter,
    GalleryFixtureResponseAdapter,
    HumanResponseAdapter,
    OpenAIResponseAdapter,
)
from opsbench.attestation import (
    load_attestation,
    sign_result_bundle,
    verify_result_attestation,
    write_attestation,
)
from opsbench.authoring import scaffold_scenario
from opsbench.backup import export_store, verify_archive, restore_archive
from opsbench.chaos import run_chaos_matrix
from opsbench.comparisons import (
    compare_bundles,
    render_markdown_comparison,
    render_markdown_leaderboard,
    rank_trials,
    summarize_trials,
)
from opsbench.contribution import check_contribution, check_gallery_contributions
from opsbench.datasets import export_public_dataset, verify_public_dataset
from opsbench.export import export_store_to_json, import_json_to_store
from opsbench.failure_injection import (
    FailureInjection,
    FailureInjectingAdapter,
    FailureMode,
    InjectedFailureError,
)
from opsbench.backup import export_store, verify_archive, restore_archive
from opsbench.prompts import render_prompt
from opsbench.mcp_adapters import MCPRegistry
from opsbench.performance_baseline import (
    PerformanceBaseline,
    PerformanceComparison,
    load_performance_baseline,
    write_performance_baseline,
)
from opsbench.performance_runner import execute_run_profiled, execute_suite_profiled
from opsbench.responses import load_response
from opsbench.recovery import run_recovery_drill, run_recovery_drill_series, run_recovery_schedule_tick
from opsbench.runner import execute_run, execute_suite, execute_suite_resilient
from opsbench.runs import ResultBundle, load_result_bundle, write_result_bundle
from opsbench.scenarios import SUPPORTED_CATEGORIES, load_gallery, load_scenario_pack
from opsbench.scoring import evaluate_response, load_evaluator_profile
from opsbench.server import create_server
from opsbench.specialized_adapters import ReliabilityReplayAdapter, load_replay_timeline
from opsbench.store import RunQuery, SQLiteResultStore
from opsbench.tracing import TraceTracer
from opsbench.validator import lint_scenario


def parse_metadata(entries: list[str] | None) -> tuple[tuple[str, str], ...]:
    """Parse repeatable metadata key=value entries into canonical run metadata."""
    metadata: list[tuple[str, str]] = []
    for entry in entries or []:
        key, separator, value = entry.partition("=")
        if not separator or not key.strip() or not value.strip():
            raise ValueError("metadata entries must use non-empty key=value format")
        metadata.append((key.strip(), value.strip()))
    if len({key for key, _ in metadata}) != len(metadata):
        raise ValueError("metadata keys must be unique")
    return tuple(sorted(metadata))


def write_performance_report(path: str | None, payload: dict[str, object]) -> None:
    """Write an optional performance report to a JSON file."""
    if path is None:
        return
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def add_performance_arguments(parser: argparse.ArgumentParser) -> None:
    """Add opt-in performance reporting and baseline controls to a run command."""
    parser.add_argument("--performance-output", help="optional performance report JSON path")
    parser.add_argument(
        "--write-performance-baseline",
        help="write the current performance measurement as a new baseline JSON file",
    )
    parser.add_argument(
        "--compare-performance-baseline",
        help="compare the current performance measurement with a baseline JSON file",
    )
    parser.add_argument(
        "--regression-threshold-percent",
        type=float,
        default=10.0,
        help="maximum wall-time increase before returning exit code 2 (default: 10)",
    )


def add_failure_injection_arguments(parser: argparse.ArgumentParser) -> None:
    """Add safe, deterministic local failure-injection controls to a run command."""
    parser.add_argument(
        "--inject-failure",
        choices=[mode.value for mode in FailureMode],
        help="inject one deterministic synthetic failure without external side effects",
    )
    parser.add_argument(
        "--inject-failure-scenario",
        action="append",
        metavar="SCENARIO_ID",
        help="apply the injected failure only to this scenario ID; repeatable",
    )


def build_parser() -> argparse.ArgumentParser:
    from opsbench import __version__

    parser = argparse.ArgumentParser(prog="opsbench")
    parser.add_argument("--version", action="version", version=f"opsbench {__version__}")
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
    prompt_parser.add_argument(
        "--mcp",
        action="append",
        help="include contextual resources from an MCP provider (e.g. jira, kubernetes, github, gitlab, grafana); repeatable",
    )
    lint_parser = scenario_subparsers.add_parser(
        "lint", help="statically lint a scenario directory for potential issues"
    )
    lint_parser.add_argument("path")
    init_parser = scenario_subparsers.add_parser(
        "init", help="scaffold a new scenario pack with authoring SDK"
    )
    init_parser.add_argument("path", help="destination directory for new scenario")
    init_parser.add_argument("--id", required=True, help="unique scenario ID (e.g. 'kubernetes-crashloop-001')")
    init_parser.add_argument("--title", default="Diagnosed scenario", help="human-readable title")
    init_parser.add_argument(
        "--category",
        choices=sorted(SUPPORTED_CATEGORIES),
        default="kubernetes",
        help="scenario category",
    )
    init_parser.add_argument("--overwrite", action="store_true", help="overwrite existing destination directory")
    check_parser = scenario_subparsers.add_parser(
        "check", help="run strict contribution readiness checks on scenario(s)"
    )
    check_parser.add_argument("path", help="scenario pack directory or gallery directory")
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
    fixture_parser.add_argument("--metadata", action="append", metavar="KEY=VALUE")
    fixture_parser.add_argument("--otlp-endpoint", help="optional OTLP/HTTP traces endpoint")
    add_performance_arguments(fixture_parser)
    add_failure_injection_arguments(fixture_parser)
    human_parser = run_subparsers.add_parser(
        "human", help="execute one locally supplied human response"
    )
    human_parser.add_argument("scenario_path")
    human_parser.add_argument("response_path")
    human_parser.add_argument("output_path")
    human_parser.add_argument("--run-id", required=True)
    human_parser.add_argument("--metadata", action="append", metavar="KEY=VALUE")
    human_parser.add_argument("--otlp-endpoint", help="optional OTLP/HTTP traces endpoint")
    add_performance_arguments(human_parser)
    add_failure_injection_arguments(human_parser)
    replay_parser = run_subparsers.add_parser(
        "replay", help="execute a run driven by a historical incident replay timeline"
    )
    replay_parser.add_argument("scenario_path")
    replay_parser.add_argument("timeline_path")
    replay_parser.add_argument("output_path")
    replay_parser.add_argument("--run-id", required=True)
    replay_parser.add_argument("--playback-speed", type=float, default=1.0)
    replay_parser.add_argument("--metadata", action="append", metavar="KEY=VALUE")
    replay_parser.add_argument("--otlp-endpoint", help="optional OTLP/HTTP traces endpoint")
    add_performance_arguments(replay_parser)
    add_failure_injection_arguments(replay_parser)
    openai_parser = run_subparsers.add_parser(
        "openai", help="execute a run against an OpenAI-compatible endpoint"
    )
    openai_parser.add_argument("scenario_path")
    openai_parser.add_argument("output_path")
    openai_parser.add_argument("--model", required=True, help="model identifier (e.g. gpt-4o, llama3)")
    openai_parser.add_argument(
        "--api-base", default="http://localhost:11434/v1", help="OpenAI-compatible API base URL"
    )
    openai_parser.add_argument("--api-key", help="optional API authorization key")
    openai_parser.add_argument("--temperature", type=float, default=0.0)
    openai_parser.add_argument("--timeout", type=float, default=60.0)
    openai_parser.add_argument("--run-id", required=True)
    openai_parser.add_argument("--metadata", action="append", metavar="KEY=VALUE")
    openai_parser.add_argument("--otlp-endpoint", help="optional OTLP/HTTP traces endpoint")
    add_performance_arguments(openai_parser)
    add_failure_injection_arguments(openai_parser)
    suite_parser = run_subparsers.add_parser(
        "suite", help="execute a response adapter across an entire scenario gallery"
    )
    suite_parser.add_argument("gallery_path")
    suite_parser.add_argument("output_dir")
    suite_parser.add_argument("--run-prefix", default="suite-run")
    suite_parser.add_argument("--max-workers", type=int, default=1, help="concurrency for gallery runs")
    suite_parser.add_argument("--metadata", action="append", metavar="KEY=VALUE")
    suite_parser.add_argument("--otlp-endpoint", help="optional OTLP/HTTP traces endpoint")
    add_performance_arguments(suite_parser)
    add_failure_injection_arguments(suite_parser)
    chaos_parser = run_subparsers.add_parser(
        "chaos-matrix", help="run a bounded local synthetic load and failure matrix"
    )
    chaos_parser.add_argument("gallery_path")
    chaos_parser.add_argument("output_dir")
    chaos_parser.add_argument("--iterations", type=int, default=1)
    chaos_parser.add_argument(
        "--mode",
        action="append",
        choices=[mode.value for mode in FailureMode],
        help="synthetic failure mode to include; repeatable",
    )
    chaos_parser.add_argument("--scenario-id", action="append", default=[])
    chaos_parser.add_argument("--max-workers", type=int, default=1)

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

    leaderboard_parser = subparsers.add_parser(
        "leaderboard", help="rank local benchmark results with uncertainty"
    )
    leaderboard_subparsers = leaderboard_parser.add_subparsers(
        dest="leaderboard_command", required=True
    )
    leaderboard_results_parser = leaderboard_subparsers.add_parser(
        "results", help="rank immutable result bundle files"
    )
    leaderboard_results_parser.add_argument("bundle_paths", nargs="+")
    leaderboard_results_parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="output format (default: json)",
    )

    store_parser = subparsers.add_parser("store", help="manage SQLite benchmark result index")
    store_subparsers = store_parser.add_subparsers(dest="store_command", required=True)
    index_parser = store_subparsers.add_parser(
        "index", help="index result bundle files into SQLite database"
    )
    index_parser.add_argument("database_path")
    index_parser.add_argument("bundle_paths", nargs="+")

    query_parser = store_subparsers.add_parser(
        "query", help="query indexed result bundles from SQLite database"
    )
    query_parser.add_argument("database_path")
    query_parser.add_argument("--scenario-id", help="filter by scenario ID")
    query_parser.add_argument("--runner-kind", help="filter by runner kind")
    query_parser.add_argument("--model-name", help="filter by model name")
    query_parser.add_argument("--limit", type=int, default=100)

    export_parser = store_subparsers.add_parser(
        "export", help="export SQLite database result bundles to a JSON package file"
    )
    export_parser.add_argument("database_path")
    export_parser.add_argument("export_path")

    import_parser = store_subparsers.add_parser(
        "import", help="import result bundles from a JSON package file into a SQLite database"
    )
    import_parser.add_argument("database_path")
    import_parser.add_argument("import_path")

    backup_parser = store_subparsers.add_parser(
        "backup", help="create a portable JSON archive of all indexed result bundles"
    )
    backup_parser.add_argument("database_path")
    backup_parser.add_argument("archive_path")

    restore_parser = store_subparsers.add_parser(
        "restore", help="restore result bundles from a portable JSON archive into a database"
    )
    restore_parser.add_argument("archive_path")
    restore_parser.add_argument("database_path")

    drill_parser = store_subparsers.add_parser(
        "drill", help="verify a local backup and recovery exercise against a fresh database"
    )
    drill_parser.add_argument("database_path")
    drill_parser.add_argument("archive_path")
    drill_parser.add_argument("restored_database_path")

    drill_series_parser = store_subparsers.add_parser(
        "drill-series", help="run repeated verified recovery drills with retention"
    )
    drill_series_parser.add_argument("database_path")
    drill_series_parser.add_argument("output_directory")
    drill_series_parser.add_argument("--attempts", type=int, default=1)
    drill_series_parser.add_argument("--retention", type=int)

    schedule_parser = store_subparsers.add_parser(
        "schedule-tick", help="run one recovery verification tick and append JSONL history"
    )
    schedule_parser.add_argument("database_path")
    schedule_parser.add_argument("output_directory")
    schedule_parser.add_argument("history_path")
    schedule_parser.add_argument("--run-id")
    schedule_parser.add_argument("--attempts", type=int, default=1)
    schedule_parser.add_argument("--retention", type=int)
    schedule_parser.add_argument("--alert-path")

    serve_parser = subparsers.add_parser("serve", help="start the OpsBench HTTP REST API server")
    serve_parser.add_argument("--host", default="127.0.0.1", help="host address to bind (default: 127.0.0.1)")
    serve_parser.add_argument("--port", type=int, default=8080, help="port to listen on (default: 8080)")
    serve_parser.add_argument("--gallery-path", default="scenarios", help="path to scenarios gallery directory")
    serve_parser.add_argument("--db", default=":memory:", help="path to SQLite result database file")
    serve_parser.add_argument(
        "--api-token",
        default=os.environ.get("OPSBENCH_API_TOKEN"),
        help="require this bearer token on all endpoints except /api/v1/health (default: $OPSBENCH_API_TOKEN)",
    )

    mcp_parser = subparsers.add_parser("mcp", help="inspect MCP platform context adapters")
    mcp_subparsers = mcp_parser.add_subparsers(dest="mcp_command", required=True)
    mcp_subparsers.add_parser("list", help="list registered MCP context adapters")
    mcp_inspect_parser = mcp_subparsers.add_parser("inspect", help="inspect tools and resources for an MCP adapter")
    mcp_inspect_parser.add_argument("provider", help="provider identifier (e.g. jira, github, gitlab, grafana, kubernetes)")

    attest_parser = subparsers.add_parser("attest", help="cryptographic signing and verification for result bundles")
    attest_subparsers = attest_parser.add_subparsers(dest="attest_command", required=True)
    sign_parser = attest_subparsers.add_parser("sign", help="sign a result bundle and emit an attestation")
    sign_parser.add_argument("bundle_path")
    sign_parser.add_argument("attestation_path")
    sign_parser.add_argument("--key", required=True, help="signing key string or secret")
    sign_parser.add_argument("--signer", required=True, help="signer identity identifier")
    sign_parser.add_argument("--metadata", action="append", metavar="KEY=VALUE")

    verify_attest_parser = attest_subparsers.add_parser("verify", help="verify a signed result attestation")
    verify_attest_parser.add_argument("bundle_path")
    verify_attest_parser.add_argument("attestation_path")
    verify_attest_parser.add_argument("--key", required=True, help="verification key string or secret")

    dataset_parser = subparsers.add_parser("dataset", help="public benchmark dataset packaging and verification")
    dataset_subparsers = dataset_parser.add_subparsers(dest="dataset_command", required=True)
    dataset_export_parser = dataset_subparsers.add_parser("export", help="export a verified public dataset bundle")
    dataset_export_parser.add_argument("gallery_path")
    dataset_export_parser.add_argument("output_path")
    dataset_export_parser.add_argument("--name", default="opsbench-standard", help="dataset name identifier")
    dataset_export_parser.add_argument("--version", default="1.0", help="dataset semantic version")

    dataset_verify_parser = dataset_subparsers.add_parser("verify", help="verify public dataset checksum and gallery agreement")
    dataset_verify_parser.add_argument("dataset_path")
    dataset_verify_parser.add_argument("--gallery-path", default=None, help="optional path to local gallery for content match")

    doctor_parser = subparsers.add_parser(
        "doctor", help="validate a scenario gallery and result database for common misconfigurations"
    )
    doctor_parser.add_argument("--gallery-path", default="scenarios", help="path to scenarios gallery directory")
    doctor_parser.add_argument("--db", default=None, help="optional path to a SQLite result database file to check")
    doctor_parser.add_argument("--archive", default=None, help="optional path to a backup archive file to validate")
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
        mcp_contexts = None
        if parsed.mcp:
            registry = MCPRegistry.create_default()
            mcp_contexts = registry.collect_context(pack, parsed.mcp)
        prompt_text = render_prompt(
            pack,
            system_instruction=parsed.instruction,
            mcp_contexts=mcp_contexts,
        )
        print(prompt_text, end="")
    if parsed.command == "scenario" and parsed.scenario_command == "lint":
        issues = lint_scenario(Path(parsed.path))
        print(
            json.dumps(
                {
                    "issue_count": len(issues),
                    "issues": issues,
                    "path": parsed.path,
                    "status": "clean" if not issues else "issues_found",
                },
                sort_keys=True,
            )
        )
    if parsed.command == "scenario" and parsed.scenario_command == "init":
        scaffold_scenario(
            scenario_id=parsed.id,
            title=parsed.title,
            category=parsed.category,
            destination=Path(parsed.path),
            overwrite=parsed.overwrite,
        )
        print(
            json.dumps(
                {
                    "category": parsed.category,
                    "destination": parsed.path,
                    "scenario_id": parsed.id,
                    "status": "scaffolded",
                },
                sort_keys=True,
            )
        )
        return 0
    if parsed.command == "scenario" and parsed.scenario_command == "check":
        target_path = Path(parsed.path)
        if (target_path / "scenario.json").is_file():
            result = check_contribution(target_path)
            print(json.dumps(result.to_dict(), sort_keys=True))
            return 0 if result.passed else 1
        elif target_path.is_dir() and any((child / "scenario.json").is_file() for child in target_path.iterdir() if child.is_dir()):
            gallery_results = check_gallery_contributions(target_path)
            all_passed = all(r.passed for r in gallery_results)
            print(
                json.dumps(
                    {
                        "all_passed": all_passed,
                        "results": [r.to_dict() for r in gallery_results],
                        "scenario_count": len(gallery_results),
                    },
                    sort_keys=True,
                )
            )
            return 0 if (gallery_results and all_passed) else 1
        else:
            result = check_contribution(target_path)
            print(json.dumps(result.to_dict(), sort_keys=True))
            return 0 if result.passed else 1
    if parsed.command == "attest" and parsed.attest_command == "sign":
        metadata = parse_metadata(parsed.metadata)
        attestation = sign_result_bundle(
            Path(parsed.bundle_path),
            parsed.key,
            parsed.signer,
            metadata=metadata,
        )
        write_attestation(Path(parsed.attestation_path), attestation)
        print(
            json.dumps(
                {
                    "attestation_path": parsed.attestation_path,
                    "bundle_hash": attestation.bundle_hash,
                    "signer_identity": attestation.signer_identity,
                    "status": "signed",
                },
                sort_keys=True,
            )
        )
        return 0
    if parsed.command == "attest" and parsed.attest_command == "verify":
        attestation = load_attestation(Path(parsed.attestation_path))
        verified = verify_result_attestation(
            Path(parsed.bundle_path),
            attestation,
            parsed.key,
        )
        print(
            json.dumps(
                {
                    "attestation_path": parsed.attestation_path,
                    "bundle_hash": attestation.bundle_hash,
                    "status": "verified" if verified else "invalid",
                    "verified": verified,
                },
                sort_keys=True,
            )
        )
        return 0 if verified else 1
    if parsed.command == "dataset" and parsed.dataset_command == "export":
        manifest = export_public_dataset(
            Path(parsed.gallery_path),
            Path(parsed.output_path),
            dataset_name=parsed.name,
            version=parsed.version,
        )
        print(
            json.dumps(
                {
                    "dataset_name": manifest.dataset_name,
                    "output_path": parsed.output_path,
                    "scenario_count": manifest.scenario_count,
                    "status": "exported",
                    "version": manifest.version,
                },
                sort_keys=True,
            )
        )
        return 0
    if parsed.command == "dataset" and parsed.dataset_command == "verify":
        verified, issues = verify_public_dataset(
            Path(parsed.dataset_path),
            Path(parsed.gallery_path) if parsed.gallery_path else None,
        )
        print(
            json.dumps(
                {
                    "dataset_path": parsed.dataset_path,
                    "issues": issues,
                    "status": "verified" if verified else "invalid",
                    "verified": verified,
                },
                sort_keys=True,
            )
        )
        return 0 if verified else 1
    if parsed.command == "response" and parsed.response_command == "evaluate":
        scenario_path = Path(parsed.scenario_path)
        pack = load_scenario_pack(scenario_path)
        profile = load_evaluator_profile(scenario_path / "evaluator.json")
        response = load_response(Path(parsed.response_path))
        report = evaluate_response(pack, profile, response)
        print(json.dumps(report.to_dict(), sort_keys=True))
    if parsed.command == "run" and parsed.run_command in {"fixture", "human", "openai", "replay"}:
        scenario_path = Path(parsed.scenario_path)
        pack = load_scenario_pack(scenario_path)
        profile = load_evaluator_profile(scenario_path / "evaluator.json")
        tracer = TraceTracer() if parsed.otlp_endpoint else None
        if parsed.run_command == "fixture":
            response = load_response(Path(parsed.response_path))
            adapter = FixtureResponseAdapter(response)
        elif parsed.run_command == "human":
            response = load_response(Path(parsed.response_path))
            adapter = HumanResponseAdapter(response)
        elif parsed.run_command == "replay":
            timeline = load_replay_timeline(Path(parsed.timeline_path))
            adapter = ReliabilityReplayAdapter(timeline, playback_speed=parsed.playback_speed)
        else:
            adapter = OpenAIResponseAdapter(
                model_name=parsed.model,
                api_base=parsed.api_base,
                api_key=parsed.api_key,
                temperature=parsed.temperature,
                timeout=parsed.timeout,
            )
        if parsed.inject_failure:
            adapter = FailureInjectingAdapter(
                adapter,
                FailureInjection(
                    FailureMode(parsed.inject_failure),
                    scenario_ids=tuple(parsed.inject_failure_scenario or ()),
                ),
            )
        performance_requested = any(
            (
                parsed.performance_output,
                parsed.write_performance_baseline,
                parsed.compare_performance_baseline,
            )
        )
        try:
            if performance_requested:
                profiled = execute_run_profiled(
                    run_id=parsed.run_id,
                    pack=pack,
                    profile=profile,
                    adapter=adapter,
                    metadata=parse_metadata(parsed.metadata),
                    tracer=tracer,
                )
                result = profiled.run_result
                current_metrics = profiled.metrics
                performance_payload = {"metrics": current_metrics.to_dict()}
            else:
                result = execute_run(
                    run_id=parsed.run_id,
                    pack=pack,
                    profile=profile,
                    adapter=adapter,
                    metadata=parse_metadata(parsed.metadata),
                    tracer=tracer,
                )
                current_metrics = None
                performance_payload = None
        except InjectedFailureError as error:
            if tracer is not None:
                tracer.export_otlp(parsed.otlp_endpoint)
            print(
                json.dumps(
                    {
                        "failure": error.to_dict(),
                        "run_id": parsed.run_id,
                        "status": "injected_failure",
                    },
                    sort_keys=True,
                )
            )
            return 3
        bundle = ResultBundle(result.run, result.report)
        output_path = Path(parsed.output_path)
        write_result_bundle(output_path, bundle)
        if tracer is not None:
            tracer.export_otlp(parsed.otlp_endpoint)
        regression_detected = False
        if current_metrics is not None and parsed.write_performance_baseline:
            write_performance_baseline(
                Path(parsed.write_performance_baseline),
                PerformanceBaseline.from_metrics(current_metrics),
            )
        if current_metrics is not None and parsed.compare_performance_baseline:
            comparison = PerformanceComparison(
                load_performance_baseline(Path(parsed.compare_performance_baseline)),
                current_metrics,
                parsed.regression_threshold_percent,
            )
            performance_payload["comparison"] = comparison.to_dict()
            regression_detected = comparison.is_regression()
        if performance_payload is not None:
            write_performance_report(parsed.performance_output, performance_payload)
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
        if regression_detected:
            return 2
    if parsed.command == "run" and parsed.run_command == "suite":
        gallery_path = Path(parsed.gallery_path)
        output_dir = Path(parsed.output_dir)
        tracer = TraceTracer() if parsed.otlp_endpoint else None
        responses: dict[str, BenchmarkResponse] = {}
        for candidate in sorted(gallery_path.iterdir(), key=lambda path: path.name):
            if candidate.is_dir() and (candidate / "scenario.json").is_file():
                response_path = candidate / "responses" / "reference-response.json"
                if not response_path.is_file():
                    raise ValueError(f"scenario missing reference response: {candidate}")
                response = load_response(response_path)
                responses[response.scenario_id] = response
        adapter = GalleryFixtureResponseAdapter(responses)
        if parsed.inject_failure:
            adapter = FailureInjectingAdapter(
                adapter,
                FailureInjection(
                    FailureMode(parsed.inject_failure),
                    scenario_ids=tuple(parsed.inject_failure_scenario or ()),
                ),
            )
        performance_requested = any(
            (
                parsed.performance_output,
                parsed.write_performance_baseline,
                parsed.compare_performance_baseline,
            )
        )
        injected_failures = ()
        if performance_requested:
            profiled_suite = execute_suite_profiled(
                gallery_directory=gallery_path,
                output_directory=output_dir,
                adapter=adapter,
                run_prefix=parsed.run_prefix,
                max_workers=parsed.max_workers,
                metadata=parse_metadata(parsed.metadata),
                tracer=tracer,
                resilient=bool(parsed.inject_failure),
            )
            bundles = profiled_suite.bundles
            injected_failures = profiled_suite.failures
            current_metrics = profiled_suite.aggregate_metrics()
            performance_payload = {
                "aggregate": current_metrics.to_dict(),
                "metrics": [metric.to_dict() for metric in profiled_suite.individual_metrics],
                "completed_count": len(bundles),
                "failed_count": len(injected_failures),
                "scenario_count": profiled_suite.scenario_count,
            }
        elif parsed.inject_failure:
            resilient_suite = execute_suite_resilient(
                gallery_directory=gallery_path,
                output_directory=output_dir,
                adapter=adapter,
                run_prefix=parsed.run_prefix,
                max_workers=parsed.max_workers,
                metadata=parse_metadata(parsed.metadata),
                tracer=tracer,
            )
            bundles = resilient_suite.bundles
            injected_failures = resilient_suite.failures
        else:
            bundles = execute_suite(
                gallery_directory=gallery_path,
                output_directory=output_dir,
                adapter=adapter,
                run_prefix=parsed.run_prefix,
                max_workers=parsed.max_workers,
                metadata=parse_metadata(parsed.metadata),
                tracer=tracer,
            )
        if tracer is not None:
            tracer.export_otlp(parsed.otlp_endpoint)
        regression_detected = False
        if performance_requested and parsed.write_performance_baseline:
            write_performance_baseline(
                Path(parsed.write_performance_baseline),
                PerformanceBaseline.from_metrics(current_metrics),
            )
        if performance_requested and parsed.compare_performance_baseline:
            comparison = PerformanceComparison(
                load_performance_baseline(Path(parsed.compare_performance_baseline)),
                current_metrics,
                parsed.regression_threshold_percent,
            )
            performance_payload["comparison"] = comparison.to_dict()
            regression_detected = comparison.is_regression()
        if performance_requested:
            write_performance_report(parsed.performance_output, performance_payload)
        print(
            json.dumps(
                {
                    "bundle_count": len(bundles),
                    "bundle_hashes": [bundle.content_hash() for bundle in bundles],
                    "failures": [failure.to_dict() for failure in injected_failures],
                    "output_dir": str(output_dir),
                    "scenario_ids": [bundle.report.scenario_id for bundle in bundles],
                    "status": (
                        "completed_with_injected_failures"
                        if injected_failures
                        else "success"
                    ),
                },
                sort_keys=True,
            )
        )
        if regression_detected:
            return 2
        if injected_failures:
            return 3
    if parsed.command == "run" and parsed.run_command == "chaos-matrix":
        modes = tuple(FailureMode(mode) for mode in (parsed.mode or [mode.value for mode in FailureMode]))
        result = run_chaos_matrix(
            Path(parsed.gallery_path),
            Path(parsed.output_dir),
            iterations=parsed.iterations,
            modes=modes,
            scenario_ids=tuple(parsed.scenario_id),
            max_workers=parsed.max_workers,
        )
        print(json.dumps(result.to_dict(), sort_keys=True))
        if result.failure_count:
            return 3
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
                                "confidence_interval_95": list(statistic.confidence_interval_95),
                                "runner_name": statistic.runner_name,
                                "standard_deviation": statistic.standard_deviation,
                                "total_score": statistic.total_score,
                                "trial_count": statistic.trial_count,
                            }
                            for statistic in trials
                        ],
                    },
                    sort_keys=True,
                )
            )
    if parsed.command == "leaderboard" and parsed.leaderboard_command == "results":
        bundles = tuple(load_result_bundle(Path(path)) for path in parsed.bundle_paths)
        if parsed.format == "markdown":
            print(render_markdown_leaderboard(bundles), end="")
        else:
            summary = compare_bundles(bundles)
            print(
                json.dumps(
                    {
                        "scenario_id": summary.scenario_id,
                        "rankings": [
                            {
                                "average_score": statistic.average_score,
                                "confidence_interval_95": list(statistic.confidence_interval_95),
                                "conservative_score": statistic.conservative_score,
                                "rank": rank,
                                "runner_name": statistic.runner_name,
                                "standard_deviation": statistic.standard_deviation,
                                "trial_count": statistic.trial_count,
                            }
                            for rank, statistic in enumerate(rank_trials(bundles), start=1)
                        ],
                    },
                    sort_keys=True,
                )
            )
    if parsed.command == "store" and parsed.store_command == "index":
        db_store = SQLiteResultStore(Path(parsed.database_path))
        indexed_count = 0
        try:
            for bundle_path in parsed.bundle_paths:
                bundle = load_result_bundle(Path(bundle_path))
                db_store.save(bundle)
                indexed_count += 1
        finally:
            db_store.close()
        print(
            json.dumps(
                {
                    "database_path": parsed.database_path,
                    "indexed_count": indexed_count,
                    "status": "success",
                },
                sort_keys=True,
            )
        )
    if parsed.command == "store" and parsed.store_command == "query":
        db_store = SQLiteResultStore(Path(parsed.database_path))
        try:
            results = db_store.query(
                RunQuery(
                    scenario_id=parsed.scenario_id,
                    runner_kind=parsed.runner_kind,
                    model_name=parsed.model_name,
                    limit=parsed.limit,
                )
            )
        finally:
            db_store.close()
        print(
            json.dumps(
                {
                    "count": len(results),
                    "database_path": parsed.database_path,
                    "results": [bundle.to_dict() for bundle in results],
                },
                sort_keys=True,
            )
        )
    if parsed.command == "store" and parsed.store_command == "export":
        db_store = SQLiteResultStore(Path(parsed.database_path))
        try:
            exported_count = export_store_to_json(db_store, Path(parsed.export_path))
        finally:
            db_store.close()
        print(
            json.dumps(
                {
                    "database_path": parsed.database_path,
                    "export_path": parsed.export_path,
                    "exported_count": exported_count,
                    "status": "success",
                },
                sort_keys=True,
            )
        )
    if parsed.command == "store" and parsed.store_command == "import":
        db_store = SQLiteResultStore(Path(parsed.database_path))
        try:
            imported_count = import_json_to_store(db_store, Path(parsed.import_path))
        finally:
            db_store.close()
        print(
            json.dumps(
                {
                    "database_path": parsed.database_path,
                    "import_path": parsed.import_path,
                    "imported_count": imported_count,
                    "status": "success",
                },
                sort_keys=True,
            )
        )
    if parsed.command == "store" and parsed.store_command == "drill":
        result = run_recovery_drill(
            Path(parsed.database_path),
            Path(parsed.archive_path),
            Path(parsed.restored_database_path),
        )
        print(json.dumps(result.to_dict(), sort_keys=True))
    if parsed.command == "store" and parsed.store_command == "drill-series":
        result = run_recovery_drill_series(
            Path(parsed.database_path),
            Path(parsed.output_directory),
            attempts=parsed.attempts,
            retention=parsed.retention,
        )
        print(json.dumps(result.to_dict(), sort_keys=True))
    if parsed.command == "store" and parsed.store_command == "schedule-tick":
        result = run_recovery_schedule_tick(
            Path(parsed.database_path),
            Path(parsed.output_directory),
            Path(parsed.history_path),
            run_id=parsed.run_id,
            attempts=parsed.attempts,
            retention=parsed.retention,
            alert_path=Path(parsed.alert_path) if parsed.alert_path else None,
        )
        print(json.dumps(result.to_dict(), sort_keys=True))
        if result.status == "failed":
            return 3
    if parsed.command == "store" and parsed.store_command == "backup":
        db_store = SQLiteResultStore(Path(parsed.database_path))
        try:
            manifest = export_store(db_store, Path(parsed.archive_path))
            print(
                json.dumps(
                    {
                        "archive_path": str(Path(parsed.archive_path)),
                        "bundle_count": manifest.bundle_count,
                        "database_path": str(Path(parsed.database_path)),
                        "status": "success",
                    },
                    sort_keys=True,
                )
            )
        finally:
            db_store.close()
    if parsed.command == "store" and parsed.store_command == "restore":
        db_store = SQLiteResultStore(Path(parsed.database_path))
        try:
            verified = verify_archive(Path(parsed.archive_path))
            restore_archive(db_store, verified)
            print(
                json.dumps(
                    {
                        "archive_path": str(Path(parsed.archive_path)),
                        "bundle_count": verified.bundle_count(),
                        "database_path": str(Path(parsed.database_path)),
                        "status": "success",
                    },
                    sort_keys=True,
                )
            )
        finally:
            db_store.close()
    if parsed.command == "serve":
        server = create_server(
            host=parsed.host,
            port=parsed.port,
            gallery_path=Path(parsed.gallery_path),
            db_path=Path(parsed.db) if parsed.db != ":memory:" else ":memory:",
            api_token=parsed.api_token,
        )
        print(f"OpsBench REST API server running on http://{parsed.host}:{parsed.port}")
        if not parsed.api_token:
            print("Warning: no --api-token configured; all endpoints are unauthenticated.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    if parsed.command == "mcp" and parsed.mcp_command == "list":
        registry = MCPRegistry.create_default()
        print(json.dumps({"providers": registry.list_providers()}, sort_keys=True))
        return 0
    if parsed.command == "mcp" and parsed.mcp_command == "inspect":
        registry = MCPRegistry.create_default()
        try:
            adapter = registry.get(parsed.provider)
            tools_data = [t.to_dict() for t in adapter.get_tool_definitions()]
            print(
                json.dumps(
                    {
                        "provider": adapter.provider_name,
                        "tool_count": len(tools_data),
                        "tools": tools_data,
                    },
                    sort_keys=True,
                )
            )
            return 0
        except KeyError as error:
            print(json.dumps({"error": str(error), "status": "not_found"}, sort_keys=True))
            return 1
    if parsed.command == "doctor":
        report: dict[str, object] = {"gallery_path": parsed.gallery_path}
        healthy = True

        try:
            gallery = load_gallery(Path(parsed.gallery_path))
            report["gallery_ok"] = True
            report["scenario_count"] = len(gallery.scenarios)
        except Exception as error:
            healthy = False
            report["gallery_ok"] = False
            report["gallery_error"] = str(error)

        if parsed.db:
            report["database_path"] = parsed.db
            try:
                doctor_store = SQLiteResultStore(parsed.db)
                try:
                    doctor_store.query(RunQuery(limit=1))
                    report["database_ok"] = True
                finally:
                    doctor_store.close()
            except Exception as error:
                healthy = False
                report["database_ok"] = False
                report["database_error"] = str(error)

        if parsed.archive:
            report["archive_path"] = parsed.archive
            try:
                verified_archive = verify_archive(Path(parsed.archive))
                report["archive_ok"] = True
                report["archive_bundle_count"] = verified_archive.bundle_count()
                report["archive_schema_version"] = verified_archive.manifest.schema_version
            except Exception as error:
                healthy = False
                report["archive_ok"] = False
                report["archive_error"] = str(error)

        report["status"] = "ok" if healthy else "error"
        print(json.dumps(report, sort_keys=True))
        return 0 if healthy else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())