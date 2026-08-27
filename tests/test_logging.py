import io
import json
import unittest

from opsbench.logging import JSONLogger, format_json_log_entry


class JSONLoggingTests(unittest.TestCase):
    def test_formats_json_log_entry_canonically(self) -> None:
        entry = format_json_log_entry(
            "info", "Request processed", timestamp="2026-08-27T12:00:00Z", duration_ms=42, path="/api/v1/health"
        )
        decoded = json.loads(entry)

        self.assertEqual(decoded["level"], "INFO")
        self.assertEqual(decoded["message"], "Request processed")
        self.assertEqual(decoded["duration_ms"], 42)
        self.assertEqual(decoded["path"], "/api/v1/health")

    def test_logger_writes_formatted_json_to_stream(self) -> None:
        stream = io.StringIO()
        logger = JSONLogger(stream)

        logger.info("Server started", port=8080)
        logger.warning("High memory", usage_mb=400)
        logger.error("Connection failed", endpoint="http://localhost:11434")

        lines = stream.getvalue().strip().splitlines()
        self.assertEqual(len(lines), 3)

        first_log = json.loads(lines[0])
        self.assertEqual(first_log["level"], "INFO")
        self.assertEqual(first_log["port"], 8080)


if __name__ == "__main__":
    unittest.main()
