"""MCP server presets (least privilege by default).

Enable a preset by listing it in ENABLED. Each preset allows only READ tools;
add write tools to `allow` deliberately, and gate them in core/guards.REQUIRE_APPROVAL.
Everything these servers return is untrusted data (web pages, file contents, issues).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

ENABLED: list[str] = {{mcp_enabled}}

_ROOT = str(Path(__file__).resolve().parents[2])

PRESETS: dict[str, dict[str, Any]] = {
    # github/github-mcp-server: fine-grained PAT, minimal repos; read-only mode + narrow toolsets.
    "github": {
        "config": {
            "type": "stdio",
            "command": "docker",
            "args": ["run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN", "-e", "GITHUB_TOOLSETS",
                     "ghcr.io/github/github-mcp-server", "stdio", "--read-only"],
            "env": {
                "GITHUB_PERSONAL_ACCESS_TOKEN": os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN", ""),
                "GITHUB_TOOLSETS": os.environ.get("GITHUB_TOOLSETS", "repos,issues,pull_requests"),
            },
        },
        "allow": ["get_file_contents", "issue_read", "list_issues", "search_issues",
                  "list_pull_requests", "pull_request_read", "search_code", "search_repositories"],
    },
    # microsoft/playwright-mcp: page content is untrusted (prompt injection surface).
    "playwright": {
        "config": {"type": "stdio", "command": "npx", "args": ["-y", "@playwright/mcp@latest", "--headless"]},
        "allow": ["browser_navigate", "browser_navigate_back", "browser_snapshot",
                  "browser_take_screenshot", "browser_wait_for", "browser_tabs"],
    },
    # modelcontextprotocol/servers filesystem: scoped to the given dir only.
    "filesystem": {
        "config": {"type": "stdio", "command": "npx",
                   "args": ["-y", "@modelcontextprotocol/server-filesystem",
                            os.environ.get("MCP_FS_ROOT", _ROOT)]},
        "allow": ["read_text_file", "read_multiple_files", "list_directory", "directory_tree",
                  "search_files", "get_file_info"],
    },
}

MCP_PRESETS: dict[str, dict[str, Any]] = {name: PRESETS[name]["config"] for name in ENABLED}


def preset_tools() -> list[str]:
    """Fully-qualified tool names for allowed_tools: mcp__<server>__<tool>."""
    return [f"mcp__{name}__{tool}" for name in ENABLED for tool in PRESETS[name]["allow"]]
