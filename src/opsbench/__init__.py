"""Reproducible benchmarks for AI-assisted DevOps."""

from opsbench.adapters import (
    FixtureResponseAdapter,
    GalleryFixtureResponseAdapter,
    HumanResponseAdapter,
    OpenAIResponseAdapter,
)
from opsbench.authoring import ScenarioBuilder, scaffold_scenario
from opsbench.chaos import ChaosCaseResult, ChaosMatrixResult, run_chaos_matrix
from opsbench.contribution import (
    ContributionCheckResult,
    check_contribution,
    check_gallery_contributions,
)
from opsbench.export import export_store_to_json, import_json_to_store
from opsbench.failure_injection import (
    FailureInjection,
    FailureInjectingAdapter,
    FailureMode,
    InjectedFailureError,
)
from opsbench.logging import JSONLogger, format_json_log_entry
from opsbench.mcp_adapters import (
    GitHubMCPAdapter,
    GitLabMCPAdapter,
    GrafanaMCPAdapter,
    JiraMCPAdapter,
    KubernetesMCPAdapter,
    MCPContextAdapter,
    MCPContextPayload,
    MCPRegistry,
    MCPResource,
    MCPToolDefinition,
)
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
from opsbench.recovery import (
    RecoveryDrillResult,
    RecoveryDrillSeriesResult,
    RecoveryScheduleResult,
    run_recovery_drill,
    run_recovery_drill_series,
    run_recovery_schedule_tick,
)
from opsbench.runner import SuiteExecution, SuiteFailure, execute_run, execute_suite, execute_suite_resilient
from opsbench.server import create_server
from opsbench.specialized_adapters import (
    ColdRouteAdapter,
    ColdRouteProfile,
    ReliabilityReplayAdapter,
    ReliabilityReplayTimeline,
    ReplayStep,
    load_cold_routes,
    load_replay_timeline,
    write_cold_routes,
    write_replay_timeline,
)
from opsbench.store import RunQuery, SQLiteResultStore
from opsbench.tracing import TraceSpan, TraceTracer
from opsbench.validator import lint_scenario
from opsbench.web import render_dashboard_html

__version__ = "0.6.2"
__all__ = [
    "ChaosCaseResult",
    "ChaosMatrixResult",
    "ColdRouteAdapter",
    "ColdRouteProfile",
    "ContributionCheckResult",
    "FixtureResponseAdapter",
    "FailureInjection",
    "FailureInjectingAdapter",
    "FailureMode",
    "GalleryFixtureResponseAdapter",
    "GitHubMCPAdapter",
    "GitLabMCPAdapter",
    "GrafanaMCPAdapter",
    "HumanResponseAdapter",
    "InjectedFailureError",
    "JSONLogger",
    "JiraMCPAdapter",
    "KubernetesMCPAdapter",
    "MCPContextAdapter",
    "MCPContextPayload",
    "MCPRegistry",
    "MCPResource",
    "MCPToolDefinition",
    "OpenAIResponseAdapter",
    "PerformanceMetrics",
    "PerformanceProfiler",
    "PerformanceBaseline",
    "PerformanceComparison",
    "ProfiledRunExecution",
    "ProfiledSuiteExecution",
    "RunQuery",
    "RecoveryDrillResult",
    "RecoveryDrillSeriesResult",
    "RecoveryScheduleResult",
    "ReliabilityReplayAdapter",
    "ReliabilityReplayTimeline",
    "ReplayStep",
    "SQLiteResultStore",
    "ScenarioBuilder",
    "SuiteExecution",
    "SuiteFailure",
    "TraceSpan",
    "TraceTracer",
    "check_contribution",
    "check_gallery_contributions",
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
    "load_cold_routes",
    "load_performance_baseline",
    "load_replay_timeline",
    "parse_response_text",
    "render_dashboard_html",
    "render_prompt",
    "run_chaos_matrix",
    "run_recovery_drill",
    "run_recovery_drill_series",
    "run_recovery_schedule_tick",
    "scaffold_scenario",
    "write_cold_routes",
    "write_performance_baseline",
    "write_replay_timeline",
]
