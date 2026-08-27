"""Structured JSON logging utilities for OpsBench platform services."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import sys
from typing import Any, TextIO


def format_json_log_entry(
    level: str,
    message: str,
    *,
    timestamp: str | None = None,
    **extra: Any,
) -> str:
    """Format a log record as a single-line canonical JSON string."""
    if not isinstance(level, str) or not level.strip():
        raise ValueError("level must be a non-empty string")
    if not isinstance(message, str):
        raise ValueError("message must be a string")

    time_str = timestamp or datetime.now(timezone.utc).isoformat()
    record: dict[str, Any] = {
        "level": level.strip().upper(),
        "message": message,
        "timestamp": time_str,
    }
    for key, value in sorted(extra.items()):
        if key not in record:
            record[key] = value

    return json.dumps(record, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


class JSONLogger:
    """Structured JSON logger writing formatted log entries to a stream."""

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream or sys.stdout

    def log(self, level: str, message: str, **extra: Any) -> None:
        entry = format_json_log_entry(level, message, **extra)
        self._stream.write(entry + "\n")
        self._stream.flush()

    def info(self, message: str, **extra: Any) -> None:
        self.log("INFO", message, **extra)

    def warning(self, message: str, **extra: Any) -> None:
        self.log("WARNING", message, **extra)

    def error(self, message: str, **extra: Any) -> None:
        self.log("ERROR", message, **extra)
