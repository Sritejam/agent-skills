"""The ONLY module that talks to the Messages API (guardrail E1).

Model pin, retries, error classification, request-id logging and cost accounting
live here, so every other module stays free of transport concerns.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import anthropic

from .config import settings

log = logging.getLogger(__name__)

# Current Claude models reject sampling params with a 400 (guardrail M2).
_FORBIDDEN_PARAMS = {"temperature", "top_p", "top_k"}

# Errors that can clear on retry. The SDK already retries these with backoff;
# we only classify them for logging/callers.
TRANSIENT_ERRORS: tuple[type[Exception], ...] = (
    anthropic.RateLimitError,  # 429
    anthropic.InternalServerError,  # 5xx incl. 529 overloaded
    anthropic.APIConnectionError,  # network + timeouts
)


class PermanentAPIError(RuntimeError):
    """400/401/403/404/413: fix the request, credentials or size; do not retry."""


@dataclass
class Ledger:
    """Per-process token ledger. `usage` on a response is per call, not cumulative."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    by_model: dict[str, int] = field(default_factory=dict)

    def add(self, model: str, usage: Any) -> None:
        self.calls += 1
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0
        self.cache_write_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0
        self.cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
        self.by_model[model] = self.by_model.get(model, 0) + 1

    @property
    def prompt_tokens(self) -> int:
        # With caching on, input_tokens is only the uncached remainder.
        return self.input_tokens + self.cache_write_tokens + self.cache_read_tokens

    def summary(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "by_model": self.by_model,
        }


def _request_id(err: anthropic.APIStatusError) -> str | None:
    rid = getattr(err, "request_id", None)
    if rid:
        return rid
    try:
        return err.response.headers.get("request-id")
    except Exception:  # pragma: no cover
        return None


class Claude:
    """Thin wrapper over anthropic.Anthropic with guardrails applied."""

    def __init__(self, model: str | None = None, *, client: Any | None = None) -> None:
        # API key comes from ANTHROPIC_API_KEY in the environment, never from code.
        self._client = client or anthropic.Anthropic(
            max_retries=settings.api_max_retries, timeout=settings.api_timeout_s
        )
        self.model = model or settings.model
        self.ledger = Ledger()

    def create(
        self,
        *,
        messages: list[dict[str, Any]],
        system: str | list[dict[str, Any]] | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
        effort: str | None = None,
        output_schema: dict[str, Any] | None = None,
        **extra: Any,
    ) -> Any:
        bad = _FORBIDDEN_PARAMS & extra.keys()
        if bad:
            raise ValueError(
                f"{sorted(bad)} are rejected by current Claude models. "
                "Steer with the prompt and `effort` instead."
            )

        model = model or self.model
        params: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens or settings.max_tokens,
            "messages": messages,
            **extra,
        }
        if system:
            params["system"] = system
        if tools:
            params["tools"] = tools

        output_config: dict[str, Any] = dict(params.pop("output_config", {}) or {})
        if effort or settings.effort:
            output_config["effort"] = effort or settings.effort
        if output_schema:
            output_config["format"] = {"type": "json_schema", "schema": output_schema}
        if output_config:
            params["output_config"] = output_config

        try:
            resp = self._client.messages.create(**params)
        except (anthropic.BadRequestError, anthropic.AuthenticationError,
                anthropic.PermissionDeniedError, anthropic.NotFoundError) as e:
            log.error("permanent API error status=%s type=%s request_id=%s",
                      e.status_code, type(e).__name__, _request_id(e))
            raise PermanentAPIError(f"{type(e).__name__} (status {e.status_code})") from e
        except anthropic.APIStatusError as e:
            log.error("API error after retries status=%s request_id=%s",
                      e.status_code, _request_id(e))
            raise
        except anthropic.APIConnectionError:
            log.error("connection/timeout error after retries")
            raise

        self.ledger.add(model, resp.usage)
        log.info(
            "claude call model=%s stop_reason=%s in=%s out=%s cache_read=%s request_id=%s",
            model,
            resp.stop_reason,
            getattr(resp.usage, "input_tokens", None),
            getattr(resp.usage, "output_tokens", None),
            getattr(resp.usage, "cache_read_input_tokens", None),
            getattr(resp, "_request_id", None),
        )
        return resp
