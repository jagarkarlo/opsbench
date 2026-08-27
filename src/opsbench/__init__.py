"""Reproducible benchmarks for AI-assisted DevOps."""

from opsbench.adapters import (
    FixtureResponseAdapter,
    GalleryFixtureResponseAdapter,
    HumanResponseAdapter,
)
from opsbench.prompts import render_prompt
from opsbench.runner import execute_run, execute_suite

__version__ = "0.1.0"
__all__ = [
    "FixtureResponseAdapter",
    "GalleryFixtureResponseAdapter",
    "HumanResponseAdapter",
    "execute_run",
    "execute_suite",
    "render_prompt",
]
