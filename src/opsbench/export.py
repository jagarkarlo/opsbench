"""Export and import utilities for benchmark result bundles and store archives."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from opsbench.runs import ResultBundle, load_result_bundle
from opsbench.store import RunQuery, SQLiteResultStore

EXPORT_SCHEMA_VERSION = "1.0"
MAX_EXPORT_FILE_BYTES = 50 * 1024 * 1024


def export_store_to_json(
    store: SQLiteResultStore,
    export_path: Path,
    filters: RunQuery | None = None,
) -> int:
    """Export result bundles from a store into a single JSON package file."""
    if not isinstance(store, SQLiteResultStore):
        raise ValueError("store must be a SQLiteResultStore")
    if not isinstance(export_path, Path):
        raise ValueError("export_path must be a Path")

    bundles = store.query(filters)
    payload = {
        "export_version": EXPORT_SCHEMA_VERSION,
        "count": len(bundles),
        "bundles": [bundle.to_dict() for bundle in bundles],
    }

    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return len(bundles)


def import_json_to_store(
    store: SQLiteResultStore,
    import_path: Path,
    *,
    max_bytes: int = MAX_EXPORT_FILE_BYTES,
) -> int:
    """Import result bundles from a JSON package file into a SQLite store."""
    if not isinstance(store, SQLiteResultStore):
        raise ValueError("store must be a SQLiteResultStore")
    if not isinstance(import_path, Path) or not import_path.is_file():
        raise ValueError(f"import_path must be a file: {import_path}")
    if import_path.stat().st_size > max_bytes:
        raise ValueError(f"import file exceeds maximum size of {max_bytes} bytes")

    try:
        decoded: Any = json.loads(import_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"import file is not valid JSON: {import_path}") from error

    if not isinstance(decoded, dict) or decoded.get("export_version") != EXPORT_SCHEMA_VERSION:
        raise ValueError(f"unsupported or missing export_version in {import_path}")

    bundles_data = decoded.get("bundles")
    if not isinstance(bundles_data, list):
        raise ValueError("export payload must contain a bundles array")

    imported_count = 0
    for bundle_dict in bundles_data:
        # Reconstruct ResultBundle using load_result_bundle logic or canonical JSON parsing
        bundle_json = json.dumps(bundle_dict)
        tmp_path = import_path.parent / ".tmp_bundle.json"
        try:
            tmp_path.write_text(bundle_json, encoding="utf-8")
            bundle = load_result_bundle(tmp_path)
            store.save(bundle)
            imported_count += 1
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    return imported_count
