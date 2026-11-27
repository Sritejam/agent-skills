"""Local OpenTelemetry tracing via Arize Phoenix (repo: Arize-ai/phoenix, ELv2 license).

Install: arize-phoenix-otel openinference-instrumentation-anthropic
Run the UI: `pip install arize-phoenix && phoenix serve` (http://localhost:6006)
Usage: call `setup()` once at startup; Anthropic SDK calls are auto-instrumented.
"""
from __future__ import annotations

import os

from phoenix.otel import register


def setup(project_name: str | None = None):
    return register(project_name=project_name or os.environ.get("PHOENIX_PROJECT", "{{name}}"),
                    auto_instrument=True)
