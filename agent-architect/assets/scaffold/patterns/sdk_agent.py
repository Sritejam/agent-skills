"""Pattern: agent on the Claude Agent SDK.

The model decides the next step in a reason-act-observe loop. This file pins down
everything the SDK leaves open: turn + budget caps, least-privilege tools, a
PreToolUse guard, explicit result handling.

Custom tools live in-process via @tool + create_sdk_mcp_server. Replace the
example tool with yours. Each description says what, when, when-NOT, and limits.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    create_sdk_mcp_server,
    query,
    tool,
)

from agent.core import load_prompt, settings
from agent.core.guards import sdk_hooks
from agent.integrations.mcp_presets import MCP_PRESETS, preset_tools

log = logging.getLogger(__name__)


# ------------------------------------------------------------------ tools

@tool(
    "lookup_record",
    "Look up a single record by its exact ID and return its fields as text. "
    "Use when the user references a specific record ID. Do NOT use for searching "
    "or listing; it needs an exact ID. Returns an error if the ID does not exist.",
    {"record_id": str},
)
async def lookup_record(args: dict[str, Any]) -> dict[str, Any]:
    record_id = args["record_id"]
    fake_db = {"42": {"name": "example", "status": "active"}}  # replace with real access
    if record_id not in fake_db:
        # Report failures as tool errors so Claude can adapt instead of crashing the loop.
        return {"content": [{"type": "text", "text": f"No record with id {record_id}"}], "is_error": True}
    return {"content": [{"type": "text", "text": str(fake_db[record_id])}]}


TOOLS_SERVER = create_sdk_mcp_server(name="app", version="1.0.0", tools=[lookup_record])

# Least privilege: list exactly what the agent may use. Add built-ins only if needed
# ("Read", "Grep", "Glob", "WebSearch", "WebFetch", "Bash", "Write", "Edit").
ALLOWED_TOOLS = ["mcp__app__lookup_record", *preset_tools()]
DISALLOWED_TOOLS = ["Bash", "Write", "Edit"]  # remove an entry only when a requirement needs it


def build_options(**overrides: Any) -> ClaudeAgentOptions:
    opts: dict[str, Any] = dict(
        model=settings.model,
        system_prompt=load_prompt("system.md"),
        mcp_servers={"app": TOOLS_SERVER, **MCP_PRESETS},
        allowed_tools=ALLOWED_TOOLS,
        disallowed_tools=DISALLOWED_TOOLS,
        permission_mode="dontAsk",  # headless: only pre-approved tools run; never bypassPermissions
        max_turns=settings.max_turns,
        max_budget_usd=settings.max_budget_usd,
        hooks=sdk_hooks(),
        setting_sources=[],  # don't inherit the developer's CLAUDE.md/settings at runtime
    )
    opts.update(overrides)
    return ClaudeAgentOptions(**opts)


class AgentRunError(RuntimeError):
    pass


async def arun(task: str) -> str:
    final: ResultMessage | None = None
    async for message in query(prompt=task, options=build_options()):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    log.debug("assistant: %s", block.text[:200])
        elif isinstance(message, ResultMessage):
            final = message

    if final is None:
        raise AgentRunError("agent ended without a result message")
    log.info("run done subtype=%s turns=%s cost_usd=%s session=%s",
             final.subtype, final.num_turns, final.total_cost_usd, final.session_id)
    # Only a success subtype carries the result text. Branch before reading it.
    if final.subtype != "success" or final.is_error:
        raise AgentRunError(f"agent stopped: {final.subtype} errors={final.errors}")
    return final.result or ""


def run(task: str) -> str:
    return asyncio.run(arun(task))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(run(" ".join(sys.argv[1:]) or sys.stdin.read()))
