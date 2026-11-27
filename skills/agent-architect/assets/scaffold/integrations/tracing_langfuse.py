"""Tracing via Langfuse (repo: langfuse/langfuse, install: langfuse).

Env: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST (cloud or self-hosted).
Usage:
    from agent.integrations.tracing_langfuse import traced, flush
    run = traced(run)      # wrap the entry point
    ... ; flush()          # before a script exits
Don't send raw PII: redact before it reaches traced functions (guardrail S5).
"""
from __future__ import annotations

from typing import Callable, TypeVar

from langfuse import get_client, observe

F = TypeVar("F", bound=Callable)


def traced(fn: F, name: str | None = None) -> F:
    return observe(name=name or fn.__name__)(fn)


def flush() -> None:
    get_client().flush()
