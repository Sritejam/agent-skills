"""The skill package must meet the Agent Skills spec and the awesome-agent-skills quality bar."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from conftest import SKILL_DIR

SKILL_MD = SKILL_DIR / "SKILL.md"
ALLOWED_KEYS = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}
ABSOLUTE_PATH = re.compile(r"/Users/[A-Za-z]|/home/[a-z]+/|~/Desktop|[A-Z]:\\\\Users")
PROMPT_KEYS = {"tags", "max_turns", "timeout_seconds", "allowed_tools"}


def frontmatter_and_body(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    assert m, f"{path.name}: missing YAML frontmatter"
    data = yaml.safe_load(m.group(1))
    assert isinstance(data, dict)
    return data, m.group(2)


def test_frontmatter_is_valid() -> None:
    fm, _ = frontmatter_and_body(SKILL_MD)
    assert set(fm) <= ALLOWED_KEYS, set(fm) - ALLOWED_KEYS
    assert fm["name"] == SKILL_DIR.name
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fm["name"]) and len(fm["name"]) <= 64
    desc = fm["description"].strip()
    assert len(desc) <= 1024 and "<" not in desc and ">" not in desc
    assert isinstance(fm.get("metadata", {}).get("version"), str), "metadata.version must be a quoted string"


def test_description_is_short_and_says_when_to_use() -> None:
    desc = frontmatter_and_body(SKILL_MD)[0]["description"]
    # awesome-agent-skills: keep top-level metadata to about 100 tokens.
    assert len(desc.split()) <= 90, len(desc.split())
    assert "Use when" in desc


def test_body_stays_under_500_lines() -> None:
    _, body = frontmatter_and_body(SKILL_MD)
    assert len(body.splitlines()) < 500


def test_exactly_one_skill_md() -> None:
    found = [p for p in SKILL_DIR.rglob("SKILL.md") if "evals" not in p.relative_to(SKILL_DIR).parts]
    assert found == [SKILL_MD]


def test_referenced_files_exist() -> None:
    text = SKILL_MD.read_text()
    refs = set(re.findall(r"`((?:references|scripts|assets)/[\w./-]+)`", text))
    assert refs, "expected SKILL.md to reference bundled files"
    missing = [r for r in sorted(refs) if not (SKILL_DIR / r).exists()]
    assert not missing, missing


def test_no_machine_specific_paths() -> None:
    offenders = []
    for p in SKILL_DIR.rglob("*"):
        if not p.is_file() or "__pycache__" in p.parts or p.suffix in {".pyc", ".png", ".jpg"}:
            continue
        if p.name == Path(__file__).name:
            continue
        # Guard tests in the template use fake paths like /home/u/.ssh on purpose.
        if p.relative_to(SKILL_DIR).parts[:4] == ("assets", "scaffold", "base", "tests"):
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if ABSOLUTE_PATH.search(line):
                offenders.append(f"{p.relative_to(SKILL_DIR)}:{i}")
    assert not offenders, offenders


# ------------------------------------------------------------------ skill eval cases

CASES = sorted(p for p in (SKILL_DIR / "evals").iterdir() if p.is_dir()) if (SKILL_DIR / "evals").is_dir() else []


def test_has_eval_cases() -> None:
    assert len(CASES) >= 3


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_eval_case_is_well_formed(case: Path) -> None:
    assert re.fullmatch(r"[a-z][a-z0-9-]*", case.name)
    settings, prompt = frontmatter_and_body(case / "prompt.md")
    assert set(settings) <= PROMPT_KEYS, set(settings) - PROMPT_KEYS
    assert prompt.strip(), "empty prompt"

    meta = yaml.safe_load((case / "case.yaml").read_text())
    assert meta["schema_version"] == "1.1" and meta["name"] == case.name
    assert meta["expected_outcome"].strip()

    graders = sorted((case / "graders").glob("*.md"))
    assert graders, "a case needs at least one grader"
    for g in graders:
        assert re.match(r"\d\d-[a-z0-9-]+\.md$", g.name), g.name
        gm, statement = frontmatter_and_body(g)
        assert gm == {"type": "llm", "focus": "trace", "weight": 1}, g.name
        assert statement.strip()

    if (case / "files").is_dir():
        assert (case / "place-files.sh").is_file()
        assert meta.get("context", {}).get("scaffold_script") == "place-files.sh"
        assert "Input files:" in prompt
