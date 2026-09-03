"""Reproducible benchmarks for AI-assisted DevOps."""

from opsbench.adapters import (
    FixtureResponseAdapter,
    GalleryFixtureResponseAdapter,
    HumanResponseAdapter,
    OpenAIResponseAdapter,
)
from opsbench.export import export_store_to_json, import_json_to_store
from opsbench.failure_injection import (
    FailureInjection,
    FailureInjectingAdapter,
    FailureMode,
    InjectedFailureError,
)
from opsbench.logging import JSONLogger, format_json_log_entry
from opsbench.metrics import generate_prometheus_metrics
from opsbench.performance import PerformanceMetrics, PerformanceProfiler
from opsbench.performance_baseline import (
    PerformanceBaseline,
    PerformanceComparison,
    load_performance_baseline,
    write_performance_baseline,
)
from opsbench.performance_runner import (
    ProfiledRunExecution,
    ProfiledSuiteExecution,
    execute_run_profiled,
    execute_suite_profiled,
)
from opsbench.prompts import render_prompt
from opsbench.responses import parse_response_text
from opsbench.recovery import RecoveryDrillResult, run_recovery_drill
from opsbench.runner import SuiteExecution, SuiteFailure, execute_run, execute_suite, execute_suite_resilient
from opsbench.server import create_server
from opsbench.store import RunQuery, SQLiteResultStore
from opsbench.tracing import TraceSpan, TraceTracer
from opsbench.validator import lint_scenario
from opsbench.web import render_dashboard_html

__version__ = "0.5.5"
__all__ = [
    "FixtureResponseAdapter",
    "FailureInjection",
    "FailureInjectingAdapter",
    "FailureMode",
    "GalleryFixtureResponseAdapter",
    "HumanResponseAdapter",
    "InjectedFailureError",
    "JSONLogger",
    "OpenAIResponseAdapter",
    "PerformanceMetrics",
    "PerformanceProfiler",
    "PerformanceBaseline",
    "PerformanceComparison",
    "ProfiledRunExecution",
    "ProfiledSuiteExecution",
    "RunQuery",
    "RecoveryDrillResult",
    "SQLiteResultStore",
    "SuiteExecution",
    "SuiteFailure",
    "TraceSpan",
    "TraceTracer",
    "create_server",
    "execute_run",
    "execute_run_profiled",
    "execute_suite",
    "execute_suite_resilient",
    "execute_suite_profiled",
    "export_store_to_json",
    "format_json_log_entry",
    "generate_prometheus_metrics",
    "import_json_to_store",
    "lint_scenario",
    "load_performance_baseline",
    "parse_response_text",
    "render_dashboard_html",
    "render_prompt",
    "run_recovery_drill",
    "write_performance_baseline",
]
