#!/usr/bin/env python3
"""Static audit for common flaws in Claude agent / LLM-app projects.

    audit.py <project-dir> [--json]

Exit 1 if any ERROR is found. Rule IDs match references/guardrails.md.
Heuristic by design: it catches the mistakes that are cheap to detect statically.
Read guardrails.md for the rest (semantic validation, approval points, PII paths).
"""
from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

SKIP_DIRS = {".venv", "venv", "env", "node_modules", ".git", "__pycache__", "site-packages",
             ".pytest_cache", "dist", "build", ".mypy_cache"}
TEXT_EXT = {".py", ".md", ".toml", ".yaml", ".yml", ".json", ".txt", ".cfg", ".ini", ".sh", ".js", ".ts"}

SECRET_RES = [
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}"), "Anthropic API key"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"), "GitHub token"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"), "Slack token"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key"),
]
SAMPLING = {"temperature", "top_p", "top_k"}


@dataclass
class Finding:
    level: str  # ERROR | WARN
    rule: str
    file: str
    line: int
    message: str


class Auditor:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.findings: list[Finding] = []

    def add(self, level: str, rule: str, path: Path | str, line: int, msg: str) -> None:
        rel = str(path.relative_to(self.root)) if isinstance(path, Path) and path.is_absolute() else str(path)
        self.findings.append(Finding(level, rule, rel, line, msg))

    def files(self, exts: set[str] | None = None):
        for p in self.root.rglob("*"):
            if any(part in SKIP_DIRS for part in p.relative_to(self.root).parts):
                continue
            if "evals/results" in str(p.relative_to(self.root)):
                continue
            if p.is_file() and (exts is None or p.suffix in exts):
                yield p

    # ------------------------------------------------------------ project-level checks

    def check_project(self) -> None:
        gi = self.root / ".gitignore"
        gi_text = gi.read_text() if gi.exists() else ""
        if not re.search(r"^\.env\s*$", gi_text, re.M):
            self.add("ERROR", "S4", ".gitignore", 0, ".env is not gitignored")
        if "settings.local.json" not in gi_text:
            self.add("WARN", "P4", ".gitignore", 0, ".claude/settings.local.json is not gitignored")
        if (self.root / ".env").exists() and not gi_text:
            self.add("ERROR", "S4", ".env", 0, ".env exists with no .gitignore")

        cm = self.root / "CLAUDE.md"
        if not cm.exists():
            self.add("WARN", "P5", "CLAUDE.md", 0, "missing CLAUDE.md (project structure + exact commands)")
        elif len(cm.read_text().splitlines()) > 200:
            self.add("WARN", "P5", "CLAUDE.md", 0, "CLAUDE.md over 200 lines; it loads in full every session")

        st = self.root / ".claude" / "settings.json"
        if not st.exists():
            self.add("WARN", "P2", ".claude/settings.json", 0, "no project settings (permissions + PreToolUse hook)")
        else:
            try:
                cfg = json.loads(st.read_text())
            except json.JSONDecodeError as e:
                self.add("ERROR", "P4", ".claude/settings.json", 0, f"invalid JSON: {e}")
                cfg = {}
            if not cfg.get("permissions", {}).get("deny"):
                self.add("WARN", "P4", ".claude/settings.json", 0, "no permissions.deny rules")
            if not cfg.get("hooks", {}).get("PreToolUse"):
                self.add("WARN", "P2", ".claude/settings.json", 0, "no PreToolUse hook for dev sessions")
            if cfg.get("permissions", {}).get("defaultMode") == "bypassPermissions":
                self.add("ERROR", "P1", ".claude/settings.json", 0, "defaultMode bypassPermissions")

        cases = self.root / "evals" / "cases.yaml"
        if not cases.exists():
            self.add("ERROR", "V1", "evals/cases.yaml", 0, "no frozen eval set")
        else:
            text = cases.read_text()
            for cat in ("representative", "boundary", "adversarial"):
                if not re.search(rf"category:\s*{cat}\b", text):
                    self.add("ERROR", "V1", "evals/cases.yaml", 0, f"no {cat} cases")

        env_ex = self.root / ".env.example"
        if env_ex.exists():
            for i, line in enumerate(env_ex.read_text().splitlines(), 1):
                m = re.match(r"\s*([A-Z0-9_]*(KEY|TOKEN|SECRET|PASSWORD|PAT))\s*=\s*(\S+)", line)
                if m:
                    self.add("ERROR", "S4", ".env.example", i, f"{m.group(1)} has a value; leave it empty")

    # ------------------------------------------------------------ text checks

    def check_secrets(self) -> None:
        for p in self.files(TEXT_EXT | {""}):
            if p.name in {".env"} or p.name.startswith(".env.") and p.name != ".env.example":
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for rx, what in SECRET_RES:
                for m in rx.finditer(text):
                    line = text.count("\n", 0, m.start()) + 1
                    self.add("ERROR", "S4", p, line, f"possible {what} committed in source")

    # ------------------------------------------------------------ python AST checks

    def check_python(self) -> None:
        for p in self.files({".py"}):
            try:
                tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
            except (SyntaxError, UnicodeDecodeError) as e:
                self.add("WARN", "-", p, 0, f"could not parse: {e}")
                continue
            PyChecks(self, p, tree).visit(tree)


def _kw_names_in(node: ast.AST) -> set[str]:
    """Keys set via dict(...) keywords or dict literals anywhere under node."""
    names: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            names |= {k.arg for k in n.keywords if k.arg}
        elif isinstance(n, ast.Dict):
            names |= {k.value for k in n.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    return names


def _call_name(node: ast.Call) -> str:
    f = node.func
    parts = []
    while isinstance(f, ast.Attribute):
        parts.append(f.attr)
        f = f.value
    if isinstance(f, ast.Name):
        parts.append(f.id)
    return ".".join(reversed(parts))


class PyChecks(ast.NodeVisitor):
    def __init__(self, auditor: Auditor, path: Path, tree: ast.AST) -> None:
        self.a, self.p, self.tree = auditor, path, tree
        self.rel = str(path.relative_to(auditor.root))
        self.is_client = self.rel.endswith(("core/client.py",))
        self.is_test = "/tests/" in f"/{self.rel}" or path.name.startswith("test_")
        self.func_stack: list[ast.AST] = []

    def err(self, rule: str, node: ast.AST, msg: str) -> None:
        self.a.add("ERROR", rule, self.p, getattr(node, "lineno", 0), msg)

    def warn(self, rule: str, node: ast.AST, msg: str) -> None:
        self.a.add("WARN", rule, self.p, getattr(node, "lineno", 0), msg)

    def _visit_func(self, node: ast.AST) -> None:
        self.func_stack.append(node)
        self._check_parse_without_stop(node)
        self.generic_visit(node)
        self.func_stack.pop()

    visit_FunctionDef = _visit_func
    visit_AsyncFunctionDef = _visit_func

    def _scope(self) -> ast.AST:
        return self.func_stack[-1] if self.func_stack else self.tree

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            if node.value == "bypassPermissions" and not self.is_test:
                self.err("P1", node, 'permission_mode "bypassPermissions" disables every permission check')
            if re.fullmatch(r"claude-[a-z0-9.-]*latest", node.value):
                self.err("M1", node, f"unpinned model alias {node.value!r}; pin an exact model ID")

    def visit_While(self, node: ast.While) -> None:
        if isinstance(node.test, ast.Constant) and node.test.value is True:
            if any(isinstance(n, ast.Call) and _call_name(n).endswith(("create", "stream", "query"))
                   for n in ast.walk(node)):
                self.err("L2", node, "`while True` around a model call; bound it with for … in range(MAX_TURNS)")
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if (isinstance(node.value, ast.Attribute) and node.value.attr == "content"
                and isinstance(node.slice, ast.Constant) and node.slice.value == 0 and not self.is_test):
            self.warn("O1", node, "content[0]: iterate blocks by type (thinking/tool_use may come first)")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node)
        kws = {k.arg for k in node.keywords if k.arg}
        has_star = any(k.arg is None for k in node.keywords)
        if has_star:
            kws |= _kw_names_in(self._scope())

        if name.endswith(("messages.create", "messages.stream", ".create")) and SAMPLING & {
                k.arg for k in node.keywords if k.arg}:
            self.err("M2", node, f"sampling params {sorted(SAMPLING & kws)} are rejected by current models")

        if not self.is_client and not self.is_test:
            if name.split(".")[-1] in ("Anthropic", "AsyncAnthropic"):
                self.warn("E1", node, "direct Anthropic client; route calls through agent.core.Claude")
            elif name.endswith("messages.create") or name.endswith("messages.stream"):
                self.warn("E1", node, "direct messages.create; route through the single client module")

        if name.split(".")[-1] == "ClaudeAgentOptions":
            for need, rule, msg in [
                ("max_turns", "L1", "no max_turns: the run is uncapped"),
                ("max_budget_usd", "L1", "no max_budget_usd: spend is uncapped"),
                ("hooks", "P2", "no hooks: register a PreToolUse guard"),
            ]:
                if need not in kws:
                    (self.err if rule == "L1" else self.warn)(rule, node, msg)
            if "allowed_tools" not in kws and "tools" not in kws:
                self.warn("P3", node, "no allowed_tools/tools list; grant least privilege explicitly")

        if name.split(".")[-1] == "AgentDefinition" and "tools" not in kws:
            self.warn("P3", node, "subagent without tools= inherits every tool")

        for k in node.keywords:
            if k.arg in ("system", "system_prompt") and isinstance(k.value, ast.JoinedStr):
                self.warn("S2", k.value, "system prompt built with an f-string; keep untrusted/per-request "
                                         "data out of it (use the user turn or tool_result)")
        self.generic_visit(node)

    def _check_parse_without_stop(self, func: ast.AST) -> None:
        src_names = {(_call_name(n)) for n in ast.walk(func) if isinstance(n, ast.Call)}
        parses = any(n.endswith("json.loads") for n in src_names)
        calls_model = any(n.endswith(("messages.create", "claude.create", ".create")) for n in src_names)
        mentions_stop = any(isinstance(n, (ast.Attribute, ast.Name)) and
                            getattr(n, "attr", getattr(n, "id", "")) in ("stop_reason", "check_stop")
                            for n in ast.walk(func))
        if parses and calls_model and not mentions_stop and not self.is_test:
            self.warn("O2", func, "parses model output without checking stop_reason first")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    root = Path(args[0] if args else ".").expanduser().resolve()
    if not root.is_dir():
        sys.exit(f"not a directory: {root}")

    a = Auditor(root)
    a.check_project()
    a.check_secrets()
    a.check_python()
    errors = [f for f in a.findings if f.level == "ERROR"]
    warns = [f for f in a.findings if f.level == "WARN"]

    if as_json:
        print(json.dumps({"errors": len(errors), "warnings": len(warns),
                          "findings": [asdict(f) for f in a.findings]}, indent=2))
    else:
        for f in sorted(a.findings, key=lambda f: (f.level != "ERROR", f.file, f.line)):
            loc = f"{f.file}:{f.line}" if f.line else f.file
            print(f"{f.level:5} {f.rule:3} {loc}  {f.message}")
        print(f"\n{len(errors)} error(s), {len(warns)} warning(s) in {root}")
        if not a.findings:
            print("clean ✔")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
