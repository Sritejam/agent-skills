#!/usr/bin/env python3
"""Claude Code PreToolUse hook for developing THIS project.

Reuses the same policy as the runtime agent (agent/core/guards.py) so dev sessions and
production share one rule set. Loads guards.py by path so it needs no installed deps.
Exit 2 = block (stderr is shown to Claude); JSON "ask" = prompt the human.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

root = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path(__file__).resolve().parents[2]))
spec = importlib.util.spec_from_file_location("guards", root / "agent" / "core" / "guards.py")
guards = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guards)

try:
    event = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(0)

verdict = guards.check_tool_call(event.get("tool_name", ""), event.get("tool_input") or {})
if verdict is None:
    sys.exit(0)

decision, reason = verdict
if decision == "deny":
    print(f"Blocked by project guard: {reason}", file=sys.stderr)
    sys.exit(2)

print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "ask",
    "permissionDecisionReason": reason,
}}))
sys.exit(0)
