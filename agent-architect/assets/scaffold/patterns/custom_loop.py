"""Pattern: hand-rolled agent loop on the Messages API.

Choose this over the Agent SDK when you must own tool execution, retries, logging
or run without the SDK runtime. The harness owns four jobs: turn accounting, state,
error handling, explicit stop conditions. Three policy seams are marked:
BEFORE a tool runs, AROUND execution, AFTER the result.
"""
from __future__ import annotations

import json
import logging
import sys
from typing import Any, Callable

from agent.core import Claude, check_stop, check_tool_call, load_prompt, settings, text_of, wrap_untrusted

log = logging.getLogger(__name__)


# ------------------------------------------------------------------ tools

# AGENT_ARCHITECT_PLACEHOLDER: example tool backed by a fake dict. Replace it with real, task-specific
# behaviour (and update TOOLS/HANDLERS); audit.py fails (V4) until this line is gone.
def lookup_record(record_id: str) -> str:
    fake_db = {"42": {"name": "example", "status": "active"}}  # replace with real access
    if record_id not in fake_db:
        raise KeyError(f"no record with id {record_id}")
    return json.dumps(fake_db[record_id], sort_keys=True)


TOOLS: list[dict[str, Any]] = [
    {
        "name": "lookup_record",
        "description": (
            "Look up a single record by its exact ID and return its fields as JSON. "
            "Use when the user references a specific record ID. Do NOT use for searching "
            "or listing; it needs an exact ID. Fails if the ID does not exist."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"record_id": {"type": "string", "description": "Exact record ID"}},
            "required": ["record_id"],
            "additionalProperties": False,
        },
        "strict": True,
    }
]

HANDLERS: dict[str, Callable[..., str]] = {"lookup_record": lookup_record}
MAX_TOOL_RESULT_CHARS = 8_000  # prune tool output before it enters history (C2)


class LoopError(RuntimeError):
    pass


def execute(name: str, args: dict[str, Any]) -> tuple[str, bool]:
    # BEFORE: deterministic policy; the model cannot argue with this.
    verdict = check_tool_call(name, args)
    if verdict:
        decision, reason = verdict
        if decision == "deny":
            return f"Denied by policy: {reason}", True
        # "ask": wire a real human-approval step here; default is to refuse.
        return f"Requires human approval: {reason}", True

    handler = HANDLERS.get(name)
    if handler is None:
        return f"Unknown tool {name}", True
    # AROUND: errors become is_error results so Claude can adapt.
    try:
        out = handler(**args)
    except Exception as e:  # noqa: BLE001 (report, don't crash the loop)
        return f"{type(e).__name__}: {e}", True
    # AFTER: prune, then deliver as data.
    if len(out) > MAX_TOOL_RESULT_CHARS:
        out = out[:MAX_TOOL_RESULT_CHARS] + "\n[truncated]"
    return out, False


def run(task: str, *, claude: Claude | None = None) -> str:
    claude = claude or Claude()
    system = load_prompt("system.md")
    messages: list[dict[str, Any]] = [{"role": "user", "content": wrap_untrusted("user", task)
                                       + "\n\nComplete the request above using the tools as needed."}]

    for turn in range(1, settings.max_turns + 1):  # bounded: never `while True` (L2)
        resp = claude.create(system=system, messages=messages, tools=TOOLS)
        check_stop(resp)
        # Echo the assistant turn back as structured blocks (keeps tool_use + thinking intact).
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            log.info("done turns=%s usage=%s", turn, claude.ledger.summary())
            return text_of(resp)

        # One user message holding a tool_result for EVERY tool_use, matched by id, results first.
        results = []
        for block in resp.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            content, is_error = execute(block.name, dict(block.input or {}))
            log.info("turn=%s tool=%s error=%s", turn, block.name, is_error)
            results.append({"type": "tool_result", "tool_use_id": block.id,
                            "content": content, "is_error": is_error})
        messages.append({"role": "user", "content": results})

    raise LoopError(f"hit max_turns={settings.max_turns} without finishing")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(run(" ".join(sys.argv[1:]) or sys.stdin.read()))
