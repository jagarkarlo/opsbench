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
from opsbench.comparisons import (
    compare_bundles,
    render_markdown_comparison,
    summarize_trials,
)
from opsbench.export import export_store_to_json, import_json_to_store
from opsbench.prompts import render_prompt
from opsbench.responses import load_response
from opsbench.runner import execute_run, execute_suite
from opsbench.runs import ResultBundle, load_result_bundle, write_result_bundle
from opsbench.scenarios import load_gallery, load_scenario_pack
from opsbench.scoring import evaluate_response, load_evaluator_profile
from opsbench.server import create_server
from opsbench.store import RunQuery, SQLiteResultStore
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
    lint_parser = scenario_subparsers.add_parser(
        "lint", help="statically lint a scenario directory for potential issues"
    )
    lint_parser.add_argument("path")
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
    human_parser = run_subparsers.add_parser(
        "human", help="execute one locally supplied human response"
    )
    human_parser.add_argument("scenario_path")
    human_parser.add_argument("response_path")
    human_parser.add_argument("output_path")
    human_parser.add_argument("--run-id", required=True)
    human_parser.add_argument("--metadata", action="append", metavar="KEY=VALUE")
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
    suite_parser = run_subparsers.add_parser(
        "suite", help="execute a response adapter across an entire scenario gallery"
    )
    suite_parser.add_argument("gallery_path")
    suite_parser.add_argument("output_dir")
    suite_parser.add_argument("--run-prefix", default="suite-run")
    suite_parser.add_argument("--max-workers", type=int, default=1, help="concurrency for gallery runs")
    suite_parser.add_argument("--metadata", action="append", metavar="KEY=VALUE")

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
    if parsed.command == "response" and parsed.response_command == "evaluate":
        scenario_path = Path(parsed.scenario_path)
        pack = load_scenario_pack(scenario_path)
        profile = load_evaluator_profile(scenario_path / "evaluator.json")
        response = load_response(Path(parsed.response_path))
        report = evaluate_response(pack, profile, response)
        print(json.dumps(report.to_dict(), sort_keys=True))
    if parsed.command == "run" and parsed.run_command in {"fixture", "human", "openai"}:
        scenario_path = Path(parsed.scenario_path)
        pack = load_scenario_pack(scenario_path)
        profile = load_evaluator_profile(scenario_path / "evaluator.json")
        if parsed.run_command == "fixture":
            response = load_response(Path(parsed.response_path))
            adapter = FixtureResponseAdapter(response)
        elif parsed.run_command == "human":
            response = load_response(Path(parsed.response_path))
            adapter = HumanResponseAdapter(response)
        else:
            adapter = OpenAIResponseAdapter(
                model_name=parsed.model,
                api_base=parsed.api_base,
                api_key=parsed.api_key,
                temperature=parsed.temperature,
                timeout=parsed.timeout,
            )
        result = execute_run(
            run_id=parsed.run_id,
            pack=pack,
            profile=profile,
            adapter=adapter,
            metadata=parse_metadata(parsed.metadata),
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
    if parsed.command == "run" and parsed.run_command == "suite":
        gallery_path = Path(parsed.gallery_path)
        output_dir = Path(parsed.output_dir)
        responses: dict[str, BenchmarkResponse] = {}
        for candidate in sorted(gallery_path.iterdir(), key=lambda path: path.name):
            if candidate.is_dir() and (candidate / "scenario.json").is_file():
                response_path = candidate / "responses" / "reference-response.json"
                if not response_path.is_file():
                    raise ValueError(f"scenario missing reference response: {candidate}")
                response = load_response(response_path)
                responses[response.scenario_id] = response
        adapter = GalleryFixtureResponseAdapter(responses)
        bundles = execute_suite(
            gallery_directory=gallery_path,
            output_directory=output_dir,
            adapter=adapter,
            run_prefix=parsed.run_prefix,
            max_workers=parsed.max_workers,
            metadata=parse_metadata(parsed.metadata),
        )
        print(
            json.dumps(
                {
                    "bundle_count": len(bundles),
                    "bundle_hashes": [bundle.content_hash() for bundle in bundles],
                    "output_dir": str(output_dir),
                    "scenario_ids": [bundle.report.scenario_id for bundle in bundles],
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())