"""Reproducible benchmarks for AI-assisted DevOps."""

from opsbench.adapters import (
    FixtureResponseAdapter,
    GalleryFixtureResponseAdapter,
    HumanResponseAdapter,
    OpenAIResponseAdapter,
)
from opsbench.export import export_store_to_json, import_json_to_store
from opsbench.logging import JSONLogger, format_json_log_entry
from opsbench.metrics import generate_prometheus_metrics
from opsbench.pipeline_view import render_pipeline_html
from opsbench.prompts import render_prompt
from opsbench.responses import parse_response_text
from opsbench.runner import execute_run, execute_suite
from opsbench.server import create_server
from opsbench.store import RunQuery, SQLiteResultStore
from opsbench.tracing import TraceSpan, TraceTracer
from opsbench.validator import lint_scenario
from opsbench.web import render_dashboard_html

__version__ = "0.1.0"
__all__ = [
    "FixtureResponseAdapter",
    "GalleryFixtureResponseAdapter",
    "HumanResponseAdapter",
    "JSONLogger",
    "OpenAIResponseAdapter",
    "RunQuery",
    "SQLiteResultStore",
    "TraceSpan",
    "TraceTracer",
    "create_server",
    "execute_run",
    "execute_suite",
    "export_store_to_json",
    "format_json_log_entry",
    "generate_prometheus_metrics",
    "import_json_to_store",
    "lint_scenario",
    "parse_response_text",
    "render_dashboard_html",
    "render_pipeline_html",
    "render_prompt",
]
