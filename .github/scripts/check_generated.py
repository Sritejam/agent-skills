#!/usr/bin/env python3
"""CI check for a freshly generated project.

    check_generated.py <audit.py> <project-dir>

1. The audit must fail with only V4 (scaffold placeholders) errors and no warnings.
2. After the placeholders are removed, the audit must pass with zero findings.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

MARKER = "AGENT_ARCHITECT_" + "PLACEHOLDER"


def run_audit(audit: str, project: Path) -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, audit, str(project), "--json"], capture_output=True, text=True)
    return proc.returncode, json.loads(proc.stdout)


def main() -> None:
    audit, project = sys.argv[1], Path(sys.argv[2])

    code, report = run_audit(audit, project)
    rules = {f["rule"] for f in report["findings"] if f["level"] == "ERROR"}
    print(f"fresh scaffold: exit={code} errors={report['errors']} warnings={report['warnings']} rules={sorted(rules)}")
    assert code == 1 and rules == {"V4"} and report["warnings"] == 0, report["findings"]

    for p in project.rglob("*.py"):
        if ".venv" in p.parts:
            continue
        lines = p.read_text().splitlines(keepends=True)
        p.write_text("".join(l for l in lines if MARKER not in l))
    cases = project / "evals" / "cases.yaml"
    cases.write_text("".join(l for l in cases.read_text().splitlines(keepends=True)
                             if not re.match(r"\s*placeholder:\s*true", l)))

    code, report = run_audit(audit, project)
    print(f"placeholders removed: exit={code} findings={len(report['findings'])}")
    assert code == 0 and not report["findings"], report["findings"]
    print("OK")


if __name__ == "__main__":
    main()
