"""scaffold.py must generate every pattern correctly and reject bad input."""
from __future__ import annotations

import os
import py_compile
import re
from pathlib import Path

import pytest

from conftest import PATTERNS, PLACEHOLDER, SKILL_DIR, audit, rules, run_script

MODEL = "claude-sonnet-5-5"
TEXT_SUFFIXES = {".py", ".md", ".toml", ".yaml", ".yml", ".json", ".example", ".txt"}
# scaffold.py's own variables (promptfoo configs legitimately use other {{...}} syntax)
SCAFFOLD_VARS = re.compile(r"\{\{(name|model|pattern|mcp_enabled|env_extra|skill_dir)\}\}")


def scaffold(dest: Path, name: str, pattern: str, *extra: str):
    return run_script("scaffold.py", "--name", name, "--dest", str(dest), "--pattern", pattern, "--model", MODEL, *extra)


def strip_placeholders(project: Path) -> None:
    for p in project.rglob("*"):
        if p.suffix == ".py" and p.is_file():
            lines = p.read_text().splitlines(keepends=True)
            p.write_text("".join(l for l in lines if PLACEHOLDER not in l))
    cases = project / "evals" / "cases.yaml"
    cases.write_text("".join(l for l in cases.read_text().splitlines(keepends=True)
                             if not re.match(r"\s*placeholder:\s*true", l)))


@pytest.mark.parametrize("pattern", PATTERNS)
def test_pattern_generates_a_complete_project(tmp_path: Path, pattern: str) -> None:
    name = "p-" + pattern.replace("_", "-")
    proc = scaffold(tmp_path, name, pattern)
    assert proc.returncode == 0, proc.stderr
    project = tmp_path / name

    for rel in ["agent/main.py", "agent/core/client.py", "agent/core/guards.py", "pyproject.toml",
                "THIRD_PARTY_NOTICES.md", "CLAUDE.md", "README.md", ".env.example", ".gitignore",
                ".claude/settings.json", "evals/cases.yaml", "evals/run_evals.py", "tests/test_guards.py"]:
        assert (project / rel).is_file(), rel
    assert os.access(project / ".claude/hooks/guard.py", os.X_OK)

    for p in project.rglob("*"):
        if p.is_file() and (p.suffix in TEXT_SUFFIXES or p.name in {".gitignore", ".env.example"}):
            assert not SCAFFOLD_VARS.search(p.read_text()), f"unrendered template variable in {p.relative_to(project)}"
        if p.suffix == ".py":
            py_compile.compile(str(p), doraise=True)

    assert MODEL in (project / "README.md").read_text()


@pytest.mark.parametrize("pattern", PATTERNS)
def test_fresh_scaffold_fails_only_on_placeholders_then_passes(tmp_path: Path, pattern: str) -> None:
    name = "p-" + pattern.replace("_", "-")
    assert scaffold(tmp_path, name, pattern).returncode == 0
    project = tmp_path / name

    code, report = audit(project)
    assert code == 1
    assert rules(report, "ERROR") == {"V4"}, report["findings"]
    assert report["errors"] == 2  # one marker in agent/main.py, one in evals/cases.yaml
    assert report["warnings"] == 0, report["findings"]

    strip_placeholders(project)
    code, report = audit(project)
    assert code == 0 and report["findings"] == [], report["findings"]


def test_claude_md_points_at_this_skill(tmp_path: Path) -> None:
    assert scaffold(tmp_path, "docs-check", "single_call").returncode == 0
    text = (tmp_path / "docs-check" / "CLAUDE.md").read_text()
    line = next(l for l in text.splitlines() if "audit.py" in l)
    assert "scripts/audit.py" in line
    try:
        SKILL_DIR.relative_to(Path.home())
        assert "~/" in line and str(Path.home()) not in line, line
    except ValueError:
        assert str(SKILL_DIR) in line, line


def test_integrations_add_deps_files_and_env(tmp_path: Path) -> None:
    proc = scaffold(tmp_path, "with-integ", "sdk_agent", "--with", "mem0,langfuse,mcp-github")
    assert proc.returncode == 0, proc.stderr
    project = tmp_path / "with-integ"
    pyproject = (project / "pyproject.toml").read_text()
    for dep in ("mem0ai", "langfuse", "claude-agent-sdk", "anthropic"):
        assert f'"{dep}"' in pyproject, dep
    assert (project / "agent/integrations/memory_mem0.py").is_file()
    assert (project / "agent/integrations/tracing_langfuse.py").is_file()
    env = (project / ".env.example").read_text()
    assert "LANGFUSE_PUBLIC_KEY=" in env and "GITHUB_PERSONAL_ACCESS_TOKEN=" in env
    notices = (project / "THIRD_PARTY_NOTICES.md").read_text()
    assert "mem0ai/mem0" in notices and "github/github-mcp-server" in notices


@pytest.mark.parametrize("bad_name", ["My_Agent", "1agent", "a", "agent name"])
def test_rejects_invalid_names(tmp_path: Path, bad_name: str) -> None:
    proc = scaffold(tmp_path, bad_name, "single_call")
    assert proc.returncode != 0
    assert not any(tmp_path.iterdir())


@pytest.mark.parametrize("bad_model", ["claude-sonnet-latest", "gpt-4o", "claude-Opus"])
def test_rejects_unpinned_or_non_claude_models(tmp_path: Path, bad_model: str) -> None:
    proc = run_script("scaffold.py", "--name", "m-check", "--dest", str(tmp_path),
                      "--pattern", "single_call", "--model", bad_model)
    assert proc.returncode != 0


def test_rejects_unknown_integration(tmp_path: Path) -> None:
    proc = scaffold(tmp_path, "bad-integ", "single_call", "--with", "redis")
    assert proc.returncode != 0 and "unknown integrations" in proc.stderr


def test_rejects_unknown_pattern(tmp_path: Path) -> None:
    proc = scaffold(tmp_path, "bad-pattern", "swarm")
    assert proc.returncode != 0


def test_refuses_non_empty_target_unless_forced(tmp_path: Path) -> None:
    target = tmp_path / "taken"
    target.mkdir()
    (target / "keep.txt").write_text("mine")
    assert scaffold(tmp_path, "taken", "single_call").returncode != 0
    assert not (target / "agent").exists()
    assert scaffold(tmp_path, "taken", "single_call", "--force").returncode == 0
    assert (target / "keep.txt").read_text() == "mine"
    assert (target / "agent/main.py").is_file()
