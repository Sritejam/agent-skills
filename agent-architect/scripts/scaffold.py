#!/usr/bin/env python3
"""Create a new agent project from the agent-architect scaffold.

    scaffold.py --name support-triage --dest ~/code --pattern sdk_agent \
        --model claude-sonnet-5-5 --with mem0,langfuse,mcp-github [--git]

Copies the shared safe core, the chosen pattern as agent/main.py, the selected
integrations, and writes pyproject.toml, .env.example and THIRD_PARTY_NOTICES.md.
Refuses to write into a non-empty directory unless --force.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SCAFFOLD = SKILL / "assets" / "scaffold"

PATTERNS = ["single_call", "workflow", "sdk_agent", "custom_loop", "orchestrator", "mcp_server"]

PATTERN_DEPS = {
    "sdk_agent": ["claude-agent-sdk"],
    "orchestrator": ["claude-agent-sdk"],
    "mcp_server": ["mcp"],
}

# flag -> (python deps, integration file or None, env lines, notice key)
INTEGRATIONS: dict[str, tuple[list[str], str | None, list[str], str]] = {
    "mem0": (["mem0ai"], "memory_mem0.py",
             ["# mem0: default embedder is OpenAI (or configure a local one)", "OPENAI_API_KEY=",
              "MEM0_LLM_MODEL=claude-haiku-4-5"], "mem0"),
    "graphiti": (["graphiti-core[anthropic]"], "memory_graphiti.py",
                 ["# graphiti: graph DB connection", "NEO4J_URI=", "NEO4J_USER=", "NEO4J_PASSWORD="], "graphiti"),
    "langfuse": (["langfuse"], "tracing_langfuse.py",
                 ["LANGFUSE_PUBLIC_KEY=", "LANGFUSE_SECRET_KEY=", "LANGFUSE_HOST=https://cloud.langfuse.com"],
                 "langfuse"),
    "phoenix": (["arize-phoenix-otel", "openinference-instrumentation-anthropic"], "tracing_phoenix.py",
                ["PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006", "PHOENIX_PROJECT="], "phoenix"),
    "mcp-github": ([], None,
                   ["# fine-grained PAT, minimal repos, read-only scopes", "GITHUB_PERSONAL_ACCESS_TOKEN=",
                    "GITHUB_TOOLSETS=repos,issues,pull_requests"], "github-mcp"),
    "mcp-playwright": ([], None, [], "playwright-mcp"),
    "mcp-filesystem": ([], None, ["# directory the filesystem MCP server may access", "MCP_FS_ROOT="],
                       "mcp-servers"),
}

NOTICES = {
    "anthropic": ("anthropics/anthropic-sdk-python", "MIT"),
    "agent-sdk": ("anthropics/claude-agent-sdk-python", "MIT"),
    "mcp": ("modelcontextprotocol/python-sdk", "MIT"),
    "mem0": ("mem0ai/mem0", "Apache-2.0"),
    "graphiti": ("getzep/graphiti", "Apache-2.0"),
    "langfuse": ("langfuse/langfuse", "MIT (ee/ directories proprietary)"),
    "phoenix": ("Arize-ai/phoenix", "Elastic License 2.0"),
    "github-mcp": ("github/github-mcp-server", "MIT"),
    "playwright-mcp": ("microsoft/playwright-mcp", "Apache-2.0"),
    "mcp-servers": ("modelcontextprotocol/servers", "MIT / Apache-2.0"),
    "promptfoo": ("promptfoo/promptfoo", "MIT"),
}

TEXT_SUFFIXES = {".py", ".md", ".toml", ".yaml", ".yml", ".json", ".example", ".txt", ""}


def render(path: Path, values: dict[str, str]) -> None:
    if path.suffix not in TEXT_SUFFIXES and path.name not in {".gitignore", ".env.example"}:
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    for key, val in values.items():
        text = text.replace("{{" + key + "}}", val)
    path.write_text(text, encoding="utf-8")


def pyproject(name: str, deps: list[str]) -> str:
    dep_lines = "\n".join(f'    "{d}",' for d in deps)
    return f"""[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "{name}"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
{dep_lines}
]

[project.optional-dependencies]
dev = ["pytest>=8"]

[tool.setuptools.packages.find]
include = ["agent*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
"""


def notices(keys: list[str]) -> str:
    rows = "\n".join(f"| {NOTICES[k][0]} | {NOTICES[k][1]} | https://github.com/{NOTICES[k][0]} |" for k in keys)
    return f"""# Third-party notices

This project depends on the following open-source projects (installed as dependencies or
run as external tools). If you copy source code from any of them into this repo, put it under
`vendor/<repo>/` together with its LICENSE file and keep its copyright headers.

| Project | License | Link |
|---|---|---|
{rows}
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True)
    ap.add_argument("--dest", required=True, help="parent directory")
    ap.add_argument("--pattern", required=True, choices=PATTERNS)
    ap.add_argument("--model", default="claude-sonnet-5-5")
    ap.add_argument("--with", dest="with_", default="", help=f"comma list of: {', '.join(INTEGRATIONS)}")
    ap.add_argument("--git", action="store_true", help="git init + first commit")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if not re.fullmatch(r"[a-z][a-z0-9-]{1,50}", args.name):
        sys.exit("name must be lowercase letters, digits and hyphens (e.g. support-triage)")
    if not re.fullmatch(r"claude-[a-z0-9-]+", args.model) or "latest" in args.model:
        sys.exit("model must be a pinned Claude model ID like claude-sonnet-5-5")
    chosen = [w.strip() for w in args.with_.split(",") if w.strip()]
    unknown = [w for w in chosen if w not in INTEGRATIONS]
    if unknown:
        sys.exit(f"unknown integrations: {unknown}. Choose from: {list(INTEGRATIONS)}")
    mcp_chosen = [w for w in chosen if w.startswith("mcp-")]
    if mcp_chosen and args.pattern not in ("sdk_agent", "orchestrator"):
        print(f"note: MCP presets are wired into sdk_agent only; for {args.pattern} connect them manually.")

    target = Path(args.dest).expanduser().resolve() / args.name
    if target.exists() and any(target.iterdir()) and not args.force:
        sys.exit(f"{target} exists and is not empty (use --force to write into it)")

    shutil.copytree(SCAFFOLD / "base", target, dirs_exist_ok=True)
    shutil.copy(SCAFFOLD / "patterns" / f"{args.pattern}.py", target / "agent" / "main.py")
    integ_dir = target / "agent" / "integrations"
    shutil.copy(SCAFFOLD / "integrations" / "mcp_presets.py", integ_dir / "mcp_presets.py")

    deps = ["anthropic", "python-dotenv", "pyyaml", *PATTERN_DEPS.get(args.pattern, [])]
    env_extra: list[str] = []
    notice_keys = ["anthropic", "promptfoo"]
    if args.pattern in ("sdk_agent", "orchestrator"):
        notice_keys.append("agent-sdk")
    if args.pattern == "mcp_server":
        notice_keys.append("mcp")
    for w in chosen:
        pdeps, fname, env_lines, nkey = INTEGRATIONS[w]
        deps += pdeps
        env_extra += env_lines
        notice_keys.append(nkey)
        if fname:
            shutil.copy(SCAFFOLD / "integrations" / fname, integ_dir / fname)

    (target / "pyproject.toml").write_text(pyproject(args.name, list(dict.fromkeys(deps))))
    (target / "THIRD_PARTY_NOTICES.md").write_text(notices(list(dict.fromkeys(notice_keys))))

    values = {
        "name": args.name,
        "model": args.model,
        "pattern": args.pattern.replace("_", " "),
        "mcp_enabled": repr([w.removeprefix("mcp-") for w in mcp_chosen]),
        "env_extra": "\n".join(env_extra),
    }
    for p in target.rglob("*"):
        if p.is_file() and ".git" not in p.parts:
            render(p, values)
    (target / ".claude" / "hooks" / "guard.py").chmod(0o755)

    if args.git:
        subprocess.run(["git", "init", "-q"], cwd=target, check=True)
        subprocess.run(["git", "add", "-A"], cwd=target, check=True)
        subprocess.run(["git", "commit", "-qm", f"Scaffold {args.name} ({args.pattern}) via agent-architect"],
                       cwd=target, check=False)

    print(f"Created {target}")
    print(f"  pattern={args.pattern} model={args.model} integrations={chosen or 'none'}")
    print("Next:")
    print(f"  cd {target} && python -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'")
    print("  cp .env.example .env   # add ANTHROPIC_API_KEY")
    print("  pytest -q && python evals/run_evals.py --dry-run")
    print(f"  python {SKILL / 'scripts' / 'audit.py'} .")


if __name__ == "__main__":
    main()
