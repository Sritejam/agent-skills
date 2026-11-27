"""Defensive output handling (guardrails O1–O4).

stop_reason first, then parse, then semantic validation, then re-prompt with the
exact error, all with a retry cap.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from .client import Claude
from .config import settings


class OutputError(RuntimeError):
    """Model output could not be turned into a valid result."""


class Truncated(OutputError):
    """stop_reason == max_tokens: raise the cap or continue the generation."""


class Refused(OutputError):
    """stop_reason == refusal: a policy decision; adjust the request, don't blindly retry."""


class ContextFull(OutputError):
    """stop_reason == model_context_window_exceeded: prune or compact history."""


def text_of(resp: Any) -> str:
    """Join text blocks. Never index content[0]: thinking/tool_use can come first."""
    return "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text")


def check_stop(resp: Any) -> None:
    reason = resp.stop_reason
    if reason in ("end_turn", "stop_sequence", "tool_use", "pause_turn"):
        return
    if reason == "max_tokens":
        raise Truncated("output hit max_tokens; result is incomplete")
    if reason == "refusal":
        raise Refused(f"model refused: {getattr(resp, 'stop_details', None)}")
    if reason == "model_context_window_exceeded":
        raise ContextFull("context window full; prune tool output or compact history")
    raise OutputError(f"unexpected stop_reason: {reason}")


Validator = Callable[[dict[str, Any]], list[str]]


def structured(
    claude: Claude,
    *,
    messages: list[dict[str, Any]],
    schema: dict[str, Any],
    system: str | None = None,
    validate: Validator | None = None,
    max_retries: int | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Generate → schema-constrained JSON → semantic validation → re-prompt on failure.

    `schema` must set additionalProperties: false on every object. Ranges, lengths and
    cross-field rules are NOT enforced by the schema layer, so put them in `validate`,
    which returns a list of human-readable error strings (empty = valid).
    """
    attempts = 1 + (settings.max_validation_retries if max_retries is None else max_retries)
    convo = list(messages)
    errors: list[str] = []
    for _ in range(attempts):
        resp = claude.create(messages=convo, system=system, output_schema=schema, **kwargs)
        check_stop(resp)  # Truncated/Refused/ContextFull are not fixed by re-prompting
        raw = text_of(resp)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            errors = [f"response was not valid JSON: {e}"]
        else:
            if not isinstance(data, dict):
                errors = ["top-level JSON value must be an object"]
            else:
                errors = validate(data) if validate else []
                if not errors:
                    return data
        convo = convo + [
            {"role": "assistant", "content": resp.content},
            {
                "role": "user",
                "content": "Your previous answer failed validation:\n- "
                + "\n- ".join(errors)
                + "\nReturn a corrected answer that fixes every listed problem.",
            },
        ]
    raise OutputError(f"still invalid after {attempts} attempts: {errors}")


def require(data: dict[str, Any], key: str, typ: type | tuple[type, ...]) -> Any:
    """Tolerant field access: fail at the boundary with a clear message, not 3 calls deep."""
    if key not in data:
        raise OutputError(f"missing field: {key}")
    if not isinstance(data[key], typ):
        raise OutputError(f"field {key!r} has type {type(data[key]).__name__}, expected {typ}")
    return data[key]
