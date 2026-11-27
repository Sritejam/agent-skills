"""Pattern: MCP server exposing tools/resources to any MCP client.

Primitives and who controls them:
  tools      model-controlled: the only primitive that acts
  resources  application-controlled read-only data, addressed by URI
  prompts    user-controlled templates (often surfaced as slash commands)

stdio transport (default): local, single user, creds from env, protocol on stdout,
logs on STDERR ONLY (printing to stdout corrupts the protocol).
For remote use: streamable-http, bind 127.0.0.1 locally, OAuth bearer in the
Authorization header, validate Origin.
"""
from __future__ import annotations

import json
import logging
import sys

from agent.core import check_tool_call

try:  # mcp main branch / 2.x
    from mcp.server import MCPServer as _Server
except ImportError:  # mcp 1.x on PyPI
    from mcp.server.fastmcp import FastMCP as _Server

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
log = logging.getLogger("{{name}}")

mcp = _Server("{{name}}")

# AGENT_ARCHITECT_PLACEHOLDER: example tool + resource backed by a fake dict. Replace them with
# real, task-specific behaviour; audit.py fails (V4) until this line is gone.
_FAKE_DB = {"42": {"name": "example", "status": "active"}}  # replace with real access


@mcp.tool()
def lookup_record(record_id: str) -> str:
    """Look up one record by exact ID and return its fields as JSON.
    Use when a specific record ID is known. Not for searching or listing.
    Raises an error if the ID does not exist."""
    verdict = check_tool_call("lookup_record", {"record_id": record_id})
    if verdict:
        raise ValueError(f"denied: {verdict[1]}")
    if record_id not in _FAKE_DB:
        raise ValueError(f"no record with id {record_id}")
    return json.dumps(_FAKE_DB[record_id], sort_keys=True)


@mcp.resource("record://{record_id}")
def record_resource(record_id: str) -> str:
    """Read-only view of a record."""
    return json.dumps(_FAKE_DB.get(record_id, {}), sort_keys=True)


def run(task: str) -> str:
    """Eval hook: lets evals/run_evals.py call a tool directly. Input: JSON {"tool": ..., "args": {...}}."""
    req = json.loads(task)
    fn = {"lookup_record": lookup_record}[req["tool"]]
    try:
        return fn(**req.get("args", {}))
    except Exception as e:  # noqa: BLE001
        return f"ERROR: {e}"


if __name__ == "__main__":
    mcp.run()  # stdio
