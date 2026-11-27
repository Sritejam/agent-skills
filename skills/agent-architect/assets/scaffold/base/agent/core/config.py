"""All runtime knobs in one place. Values come from env (.env in dev), never hard-coded secrets.

Changing the model is a one-line, reviewable change here (or MODEL in .env), and it
should always be followed by `python evals/run_evals.py` against the baseline.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:  # optional: load .env in development
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:  # pragma: no cover
    pass


def _f(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


def _i(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


@dataclass(frozen=True)
class Settings:
    # Pinned model IDs. Never use "-latest" style aliases.
    model: str = os.environ.get("MODEL", "{{model}}")
    fast_model: str = os.environ.get("FAST_MODEL", "claude-haiku-5-5")  # routing/classification/judges

    # Hard bounds: an unbounded loop is a defect (guardrail L1/L2).
    max_turns: int = _i("MAX_TURNS", 20)
    max_budget_usd: float = _f("MAX_BUDGET_USD", 1.00)
    max_tokens: int = _i("MAX_TOKENS", 4096)
    max_validation_retries: int = _i("MAX_VALIDATION_RETRIES", 2)
    max_concurrency: int = _i("MAX_CONCURRENCY", 4)

    # Retries for transient errors only (429/5xx/timeouts) are done by the Anthropic SDK.
    api_max_retries: int = _i("API_MAX_RETRIES", 3)
    api_timeout_s: float = _f("API_TIMEOUT_S", 600)

    # "high" is the API default. Lower it for cheap steps before switching models.
    effort: str | None = os.environ.get("EFFORT") or None


settings = Settings()

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


def load_prompt(name: str) -> str:
    """Prompts are versioned files, reviewed like code (guardrail M3)."""
    return (PROMPTS_DIR / name).read_text(encoding="utf-8").strip()
