"""audit.py must flag each known flaw with the right rule ID, and nothing on clean code."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import PLACEHOLDER, audit, rules, run_script, write


def test_clean_project_passes(clean_project: Path) -> None:
    code, report = audit(clean_project)
    assert code == 0, report
    assert report["findings"] == []


def test_human_output_and_exit_code(clean_project: Path) -> None:
    proc = run_script("audit.py", str(clean_project))
    assert proc.returncode == 0
    assert "clean" in proc.stdout


def test_missing_directory_is_an_error(tmp_path: Path) -> None:
    proc = run_script("audit.py", str(tmp_path / "nope"))
    assert proc.returncode != 0


# ------------------------------------------------------------------ errors (exit 1)

ERROR_CASES = {
    "L1-no-turn-or-budget-cap": (
        "agent/main.py",
        "from claude_agent_sdk import ClaudeAgentOptions\nopts = ClaudeAgentOptions(model='m', hooks={})\n",
        "L1",
    ),
    "L2-unbounded-loop": (
        "agent/main.py",
        "def go(client):\n    while True:\n        client.messages.create(model='m', messages=[])\n",
        "L2",
    ),
    "M1-unpinned-model-alias": ("agent/main.py", "MODEL = 'claude-3-5-sonnet-latest'\n", "M1"),
    "M2-sampling-params": (
        "agent/core/client.py",
        "def go(client):\n    return client.messages.create(model='m', messages=[], temperature=0.2)\n",
        "M2",
    ),
    "P1-bypass-permissions-in-code": ("agent/main.py", "MODE = 'bypassPermissions'\n", "P1"),
    "V4-placeholder-in-code": ("agent/main.py", f"# {PLACEHOLDER}: replace me\nX = 1\n", "V4"),
}


@pytest.mark.parametrize("case", list(ERROR_CASES))
def test_flags_code_errors(clean_project: Path, case: str) -> None:
    rel, src, rule = ERROR_CASES[case]
    write(clean_project, rel, src)
    code, report = audit(clean_project)
    assert code == 1
    assert rule in rules(report, "ERROR"), report["findings"]


def test_flags_committed_secret(clean_project: Path) -> None:
    # Built at runtime so this test file never contains a key-shaped string.
    fake_key = "sk-ant-" + "x" * 24
    write(clean_project, "agent/config.py", f"KEY = '{fake_key}'\n")
    code, report = audit(clean_project)
    assert code == 1 and "S4" in rules(report, "ERROR")


def test_secret_in_local_env_file_is_ignored(clean_project: Path) -> None:
    write(clean_project, ".env", "ANTHROPIC_API_KEY=sk-ant-" + "y" * 24 + "\n")
    code, report = audit(clean_project)
    assert code == 0, report["findings"]


def test_flags_env_not_gitignored(clean_project: Path) -> None:
    write(clean_project, ".gitignore", ".claude/settings.local.json\n")
    code, report = audit(clean_project)
    assert code == 1 and "S4" in rules(report, "ERROR")


def test_flags_value_in_env_example(clean_project: Path) -> None:
    write(clean_project, ".env.example", "ANTHROPIC_API_KEY=abc123\n")
    code, report = audit(clean_project)
    assert code == 1 and "S4" in rules(report, "ERROR")


def test_flags_bypass_permissions_in_settings(clean_project: Path) -> None:
    cfg = json.loads((clean_project / ".claude/settings.json").read_text())
    cfg["permissions"]["defaultMode"] = "bypassPermissions"
    write(clean_project, ".claude/settings.json", json.dumps(cfg))
    code, report = audit(clean_project)
    assert code == 1 and "P1" in rules(report, "ERROR")


def test_flags_missing_eval_set(clean_project: Path) -> None:
    (clean_project / "evals/cases.yaml").unlink()
    code, report = audit(clean_project)
    assert code == 1 and "V1" in rules(report, "ERROR")


def test_flags_missing_adversarial_category(clean_project: Path) -> None:
    text = (clean_project / "evals/cases.yaml").read_text().replace("category: adversarial", "category: boundary")
    write(clean_project, "evals/cases.yaml", text)
    code, report = audit(clean_project)
    assert code == 1 and "V1" in rules(report, "ERROR")


def test_flags_placeholder_eval_cases(clean_project: Path) -> None:
    text = (clean_project / "evals/cases.yaml").read_text().replace("- id: rep-1\n", "- id: rep-1\n  placeholder: true\n")
    write(clean_project, "evals/cases.yaml", text)
    code, report = audit(clean_project)
    assert code == 1 and "V4" in rules(report, "ERROR")


# ------------------------------------------------------------------ warnings (exit 0)

WARN_CASES = {
    "E1-direct-client": ("agent/main.py", "import anthropic\nc = anthropic.Anthropic()\n", "E1"),
    "O1-content-index-zero": ("agent/main.py", "def f(resp):\n    return resp.content[0].text\n", "O1"),
    "O2-parse-without-stop-check": (
        "agent/main.py",
        "import json\ndef f(claude):\n    r = claude.create(messages=[])\n    return json.loads(r)\n",
        "O2",
    ),
    "P3-subagent-without-tools": (
        "agent/main.py",
        "from claude_agent_sdk import AgentDefinition\nw = AgentDefinition(description='d', prompt='p')\n",
        "P3",
    ),
    "S2-fstring-system-prompt": (
        "agent/main.py",
        "def f(client, user):\n    client.messages.create(model='m', messages=[], system=f'Hi {user}')\n",
        "S2",
    ),
}


@pytest.mark.parametrize("case", list(WARN_CASES))
def test_flags_warnings_without_failing(clean_project: Path, case: str) -> None:
    rel, src, rule = WARN_CASES[case]
    write(clean_project, rel, src)
    code, report = audit(clean_project)
    assert code == 0, report["findings"]
    assert rule in rules(report, "WARN"), report["findings"]


def test_test_files_are_exempt_from_p1(clean_project: Path) -> None:
    write(clean_project, "tests/test_modes.py", "MODE = 'bypassPermissions'\n")
    code, report = audit(clean_project)
    assert code == 0, report["findings"]


def test_eval_results_are_not_scanned(clean_project: Path) -> None:
    write(clean_project, "evals/results/run.json", '{"leak": "sk-ant-' + "z" * 24 + '"}')
    code, report = audit(clean_project)
    assert code == 0, report["findings"]
