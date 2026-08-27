"""Storage and query interfaces for indexable benchmark result bundles."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Protocol, Sequence

from opsbench.runs import BenchmarkRun, ResultBundle, load_result_bundle
from opsbench.scoring import Score, ScoreReport


@dataclass(frozen=True)
class RunQuery:
    """Filter parameters for querying benchmark results."""

    scenario_id: str | None = None
    runner_kind: str | None = None
    model_name: str | None = None
    limit: int = 100

    def __post_init__(self) -> None:
        if self.limit <= 0:
            raise ValueError("limit must be a positive integer")


class ResultStore(Protocol):
    """Abstract persistence interface for result bundles."""

    def save(self, bundle: ResultBundle) -> None:
        """Persist a result bundle into the store."""

    def get(self, run_id: str) -> ResultBundle | None:
        """Retrieve a result bundle by its run_id."""

    def query(self, filters: RunQuery | None = None) -> tuple[ResultBundle, ...]:
        """Query result bundles matching the given filters."""


class SQLiteResultStore:
    """Zero-dependency SQLite-backed result store for indexing benchmark runs."""

    def __init__(self, database_path: Path | str = ":memory:") -> None:
        self._path = str(database_path)
        self._connection = sqlite3.connect(self._path)
        self._connection.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS result_bundles (
                    run_id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL,
                    runner_kind TEXT NOT NULL,
                    model_name TEXT,
                    started_at TEXT NOT NULL,
                    total_score INTEGER NOT NULL,
                    maximum_score INTEGER NOT NULL,
                    bundle_hash TEXT NOT NULL,
                    bundle_json TEXT NOT NULL
                )
                """
            )
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_scenario ON result_bundles (scenario_id)"
            )
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_runner ON result_bundles (runner_kind)"
            )

    def save(self, bundle: ResultBundle) -> None:
        if not isinstance(bundle, ResultBundle):
            raise ValueError("bundle must be a ResultBundle")

        run_id = bundle.run.run_id
        scenario_id = bundle.report.scenario_id
        runner_kind = bundle.run.runner_kind
        model_name = bundle.run.model_name
        started_at = bundle.run.started_at
        total_score = bundle.report.total
        maximum_score = bundle.report.maximum
        bundle_hash = bundle.content_hash()
        bundle_json = bundle.canonical_json()

        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO result_bundles (
                        run_id, scenario_id, runner_kind, model_name,
                        started_at, total_score, maximum_score, bundle_hash, bundle_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        scenario_id,
                        runner_kind,
                        model_name,
                        started_at,
                        total_score,
                        maximum_score,
                        bundle_hash,
                        bundle_json,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise ValueError(f"result bundle with run_id {run_id!r} already exists in store") from error

    def get(self, run_id: str) -> ResultBundle | None:
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("run_id must be a non-empty string")

        cursor = self._connection.execute(
            "SELECT bundle_json FROM result_bundles WHERE run_id = ?", (run_id.strip(),)
        )
        row = cursor.fetchone()
        if row is None:
            return None

        return self._decode_bundle(row["bundle_json"])

    def query(self, filters: RunQuery | None = None) -> tuple[ResultBundle, ...]:
        query_filters = filters or RunQuery()
        conditions: list[str] = []
        params: list[str | int] = []

        if query_filters.scenario_id:
            conditions.append("scenario_id = ?")
            params.append(query_filters.scenario_id)
        if query_filters.runner_kind:
            conditions.append("runner_kind = ?")
            params.append(query_filters.runner_kind)
        if query_filters.model_name:
            conditions.append("model_name = ?")
            params.append(query_filters.model_name)

        where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT bundle_json FROM result_bundles{where_clause} ORDER BY started_at DESC LIMIT ?"
        params.append(query_filters.limit)

        cursor = self._connection.execute(sql, params)
        rows = cursor.fetchall()
        return tuple(self._decode_bundle(row["bundle_json"]) for row in rows)

    def count(self) -> int:
        cursor = self._connection.execute("SELECT COUNT(*) FROM result_bundles")
        return cursor.fetchone()[0]

    def close(self) -> None:
        self._connection.close()

    def _decode_bundle(self, bundle_json: str) -> ResultBundle:
        decoded = json.loads(bundle_json)
        run_fields = decoded["run"]
        metadata = run_fields.get("metadata", {})
        run = BenchmarkRun(
            **{k: v for k, v in run_fields.items() if k != "metadata"},
            metadata=tuple(metadata.items()),
        )
        report_fields = decoded["report"]
        report = ScoreReport(
            scenario_id=report_fields["scenario_id"],
            response_hash=report_fields["response_hash"],
            diagnosis=Score(report_fields["diagnosis"]),
            evidence=Score(report_fields["evidence"]),
            actions=Score(report_fields["actions"]),
            safety=Score(report_fields["safety"]),
            explanation=report_fields["explanation"],
        )
        return ResultBundle(run, report)
