"""Reproducible benchmarks for AI-assisted DevOps."""

from opsbench.adapters import (
    FixtureResponseAdapter,
    GalleryFixtureResponseAdapter,
    HumanResponseAdapter,
    OpenAIResponseAdapter,
)
from opsbench.prompts import render_prompt
from opsbench.responses import parse_response_text
from opsbench.runner import execute_run, execute_suite
from opsbench.server import create_server
from opsbench.store import RunQuery, SQLiteResultStore

__version__ = "0.1.0"
__all__ = [
    "FixtureResponseAdapter",
    "GalleryFixtureResponseAdapter",
    "HumanResponseAdapter",
    "OpenAIResponseAdapter",
    "RunQuery",
    "SQLiteResultStore",
    "create_server",
    "execute_run",
    "execute_suite",
    "parse_response_text",
    "render_prompt",
]
