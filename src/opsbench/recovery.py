"""Local backup and recovery drill orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from opsbench.backup import export_store, restore_archive, verify_archive
from opsbench.store import RunQuery, SQLiteResultStore


@dataclass(frozen=True)
class RecoveryDrillResult:
    """Verified outcome of exporting and restoring a local result store."""

    archive_path: str
    archive_sha256: str
    restored_bundle_hashes: tuple[str, ...]
    restored_count: int
    source_count: int

    def __post_init__(self) -> None:
        if self.source_count < 0 or self.restored_count < 0:
            raise ValueError("bundle counts must be non-negative")
        if self.source_count != self.restored_count:
            raise ValueError("source and restored bundle counts must match")
        if len(self.restored_bundle_hashes) != self.restored_count:
            raise ValueError("restored bundle hash count must match restored_count")

    def to_dict(self) -> dict[str, object]:
        return {
            "archive_path": self.archive_path,
            "archive_sha256": self.archive_sha256,
            "restored_bundle_hashes": list(self.restored_bundle_hashes),
            "restored_count": self.restored_count,
            "source_count": self.source_count,
            "status": "verified",
        }


@dataclass(frozen=True)
class RecoveryDrillSeriesResult:
    """Verified outcomes and retention summary for repeated local recovery drills."""

    attempts: tuple[RecoveryDrillResult, ...]
    retained_attempts: int
    removed_attempts: int

    def __post_init__(self) -> None:
        if not isinstance(self.attempts, tuple) or not all(
            isinstance(attempt, RecoveryDrillResult) for attempt in self.attempts
        ):
            raise ValueError("attempts must be a tuple of RecoveryDrillResult values")
        if not isinstance(self.retained_attempts, int) or self.retained_attempts < 0:
            raise ValueError("retained_attempts must be a non-negative integer")
        if not isinstance(self.removed_attempts, int) or self.removed_attempts < 0:
            raise ValueError("removed_attempts must be a non-negative integer")
        if self.retained_attempts + self.removed_attempts != len(self.attempts):
            raise ValueError("retention counts must match attempt count")

    def to_dict(self) -> dict[str, object]:
        return {
            "attempts": [attempt.to_dict() for attempt in self.attempts],
            "attempt_count": len(self.attempts),
            "removed_attempts": self.removed_attempts,
            "retained_attempts": self.retained_attempts,
            "status": "verified",
        }


@dataclass(frozen=True)
class RecoveryScheduleResult:
    """Outcome of one externally scheduled recovery-drill invocation."""

    run_id: str
    status: str
    history_path: str
    alert_path: str | None = None
    series: RecoveryDrillSeriesResult | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ValueError("run_id must be a non-empty string")
        if self.status not in {"verified", "failed"}:
            raise ValueError("status must be verified or failed")
        if not isinstance(self.history_path, str) or not self.history_path.strip():
            raise ValueError("history_path must be a non-empty string")
        if self.status == "verified" and self.series is None:
            raise ValueError("verified schedule results must include a series")
        if self.status == "failed" and not self.error:
            raise ValueError("failed schedule results must include an error")

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "alert_path": self.alert_path,
            "error": self.error,
            "history_path": self.history_path,
            "run_id": self.run_id,
            "status": self.status,
        }
        if self.series is not None:
            payload["series"] = self.series.to_dict()
        return payload


def run_recovery_drill(
    source_database_path: Path, archive_path: Path, restored_database_path: Path
) -> RecoveryDrillResult:
    """Export a database, restore it into a fresh database, and verify exact bundle hashes."""
    for field_name, path in (
        ("source_database_path", source_database_path),
        ("archive_path", archive_path),
        ("restored_database_path", restored_database_path),
    ):
        if not isinstance(path, Path):
            raise ValueError(f"{field_name} must be a Path")
    if not source_database_path.is_file():
        raise ValueError(f"source database must be a file: {source_database_path}")
    if restored_database_path.exists():
        raise ValueError(f"restored database must not already exist: {restored_database_path}")

    source_store = SQLiteResultStore(source_database_path)
    try:
        source_bundles = source_store.query(RunQuery(limit=2**31 - 1))
        manifest = export_store(source_store, archive_path)
    finally:
        source_store.close()

    archive = verify_archive(archive_path)
    restored_store = SQLiteResultStore(restored_database_path)
    try:
        restore_archive(restored_store, archive)
        restored_bundles = restored_store.query(RunQuery(limit=2**31 - 1))
    finally:
        restored_store.close()

    source_hashes = tuple(sorted(bundle.content_hash() for bundle in source_bundles))
    restored_hashes = tuple(sorted(bundle.content_hash() for bundle in restored_bundles))
    if source_hashes != restored_hashes:
        raise ValueError("restored bundle hashes do not match the source database")

    return RecoveryDrillResult(
        archive_path=str(archive_path),
        archive_sha256=manifest.archive_sha256,
        restored_bundle_hashes=restored_hashes,
        restored_count=len(restored_bundles),
        source_count=len(source_bundles),
    )


def run_recovery_drill_series(
    source_database_path: Path,
    output_directory: Path,
    *,
    attempts: int = 1,
    retention: int | None = None,
) -> RecoveryDrillSeriesResult:
    """Run numbered recovery drills and retain only the newest verified attempts."""
    if not isinstance(source_database_path, Path):
        raise ValueError("source_database_path must be a Path")
    if not isinstance(output_directory, Path):
        raise ValueError("output_directory must be a Path")
    if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts <= 0:
        raise ValueError("attempts must be a positive integer")
    if retention is None:
        retention = attempts
    if not isinstance(retention, int) or isinstance(retention, bool) or retention <= 0:
        raise ValueError("retention must be a positive integer")
    if retention > attempts:
        raise ValueError("retention must not exceed attempts")

    output_directory.mkdir(parents=True, exist_ok=True)
    results: list[RecoveryDrillResult] = []
    for attempt_number in range(1, attempts + 1):
        attempt_directory = output_directory / f"attempt-{attempt_number:04d}"
        if attempt_directory.exists():
            raise ValueError(f"recovery attempt directory already exists: {attempt_directory}")
        attempt_directory.mkdir()
        try:
            result = run_recovery_drill(
                source_database_path,
                attempt_directory / "backup.json",
                attempt_directory / "restored.db",
            )
        except Exception:
            shutil.rmtree(attempt_directory)
            raise
        results.append(result)

    removed_attempts = attempts - retention
    for result in results[:removed_attempts]:
        shutil.rmtree(Path(result.archive_path).parent)

    return RecoveryDrillSeriesResult(
        attempts=tuple(results),
        retained_attempts=retention,
        removed_attempts=removed_attempts,
    )


def run_recovery_schedule_tick(
    source_database_path: Path,
    output_directory: Path,
    history_path: Path,
    *,
    run_id: str | None = None,
    attempts: int = 1,
    retention: int | None = None,
    alert_path: Path | None = None,
) -> RecoveryScheduleResult:
    """Run one cron-friendly recovery tick and append a durable outcome record."""
    for field_name, path in (
        ("source_database_path", source_database_path),
        ("output_directory", output_directory),
        ("history_path", history_path),
    ):
        if not isinstance(path, Path):
            raise ValueError(f"{field_name} must be a Path")
    if alert_path is not None and not isinstance(alert_path, Path):
        raise ValueError("alert_path must be a Path or None")
    if run_id is None:
        run_id = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%S%fZ")
    if not isinstance(run_id, str) or not run_id.strip() or Path(run_id).name != run_id:
        raise ValueError("run_id must be a non-empty filename-safe value")

    run_directory = output_directory / run_id
    try:
        series = run_recovery_drill_series(
            source_database_path,
            run_directory,
            attempts=attempts,
            retention=retention,
        )
        result = RecoveryScheduleResult(
            run_id=run_id,
            status="verified",
            history_path=str(history_path),
            alert_path=str(alert_path) if alert_path is not None else None,
            series=series,
        )
        if alert_path is not None and alert_path.exists():
            alert_path.unlink()
    except Exception as error:
        result = RecoveryScheduleResult(
            run_id=run_id,
            status="failed",
            history_path=str(history_path),
            alert_path=str(alert_path) if alert_path is not None else None,
            error=str(error),
        )
        if alert_path is not None:
            alert_path.parent.mkdir(parents=True, exist_ok=True)
            alert_path.write_text(json.dumps(result.to_dict(), sort_keys=True) + "\n", encoding="utf-8")

    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as history_file:
        history_file.write(json.dumps(result.to_dict(), sort_keys=True) + "\n")
    return result
