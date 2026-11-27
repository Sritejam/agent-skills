"""Frozen-eval runner + regression gate (guardrails V1, V2).

    python evals/run_evals.py                  # run all cases
    python evals/run_evals.py --category adversarial
    python evals/run_evals.py --dry-run        # validate cases.yaml, no API calls
    python evals/run_evals.py --save-baseline  # accept this run as the new baseline

Exit 1 if any adversarial case fails or the pass rate drops below evals/baseline.json.
Every case calls the agent (and `judge` cases call a model too), so runs cost money.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CASES = ROOT / "evals" / "cases.yaml"
BASELINE = ROOT / "evals" / "baseline.json"
RESULTS = ROOT / "evals" / "results"
CATEGORIES = {"representative", "boundary", "adversarial"}


def load_cases() -> list[dict[str, Any]]:
    cases = yaml.safe_load(CASES.read_text()) or []
    problems = []
    seen = set()
    for c in cases:
        if c.get("id") in seen:
            problems.append(f"duplicate id {c.get('id')}")
        seen.add(c.get("id"))
        if c.get("category") not in CATEGORIES:
            problems.append(f"{c.get('id')}: category must be one of {sorted(CATEGORIES)}")
        if "input" not in c:
            problems.append(f"{c.get('id')}: missing input")
    missing = CATEGORIES - {c.get("category") for c in cases}
    if missing:
        problems.append(f"no cases for categories: {sorted(missing)}")
    if problems:
        sys.exit("cases.yaml problems:\n- " + "\n- ".join(problems))
    return cases


def judge(output: str, rubric: str) -> tuple[bool, str]:
    from agent.core import Claude, settings, structured, wrap_untrusted

    data = structured(
        Claude(settings.fast_model),
        messages=[{"role": "user", "content": wrap_untrusted("agent_output", output)
                   + f"\n\nGrade the output above against this rubric: {rubric}"}],
        schema={"type": "object",
                "properties": {"verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
                               "reason": {"type": "string"}},
                "required": ["verdict", "reason"], "additionalProperties": False},
    )
    return data["verdict"] == "PASS", data["reason"]


def check(case: dict[str, Any], output: str | None, error: str | None) -> list[str]:
    exp = case.get("expect", {}) or {}
    if error is not None:
        return [] if exp.get("allow_error") else [f"raised {error}"]
    fails = []
    low = output.lower()
    for s in exp.get("contains", []):
        if s.lower() not in low:
            fails.append(f"missing {s!r}")
    for s in exp.get("not_contains", []):
        if s.lower() in low:
            fails.append(f"contains forbidden {s!r}")
    if "json" in exp:
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            fails.append("output is not JSON")
        else:
            for k, v in exp["json"].items():
                if data.get(k) != v:
                    fails.append(f"json.{k}={data.get(k)!r}, expected {v!r}")
    if "judge" in exp and not fails:
        ok, reason = judge(output, exp["judge"])
        if not ok:
            fails.append(f"judge: {reason}")
    return fails


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", choices=sorted(CATEGORIES))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--save-baseline", action="store_true")
    args = ap.parse_args()

    cases = load_cases()
    if args.category:
        cases = [c for c in cases if c["category"] == args.category]
    if args.dry_run:
        print(f"{len(cases)} cases OK")
        return

    from agent.main import run

    rows = []
    for c in cases:
        t0 = time.time()
        output, error = None, None
        try:
            output = run(c["input"])
        except Exception as e:  # noqa: BLE001
            error = f"{type(e).__name__}: {e}"
        fails = check(c, output, error)
        rows.append({"id": c["id"], "category": c["category"], "passed": not fails,
                     "fails": fails, "seconds": round(time.time() - t0, 2),
                     "output": (output or "")[:2000]})
        print(f"{'PASS' if not fails else 'FAIL'}  [{c['category']}] {c['id']}  {'; '.join(fails)}")

    by_cat: dict[str, list[bool]] = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r["passed"])
    summary = {
        "pass_rate": round(sum(r["passed"] for r in rows) / max(len(rows), 1), 4),
        "by_category": {k: round(sum(v) / len(v), 4) for k, v in by_cat.items()},
        "n": len(rows),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{int(time.time())}.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    print(json.dumps(summary, indent=2))

    if args.save_baseline:
        BASELINE.write_text(json.dumps(summary, indent=2))
        print("baseline saved")
        return

    failed = False
    if any(not r["passed"] for r in rows if r["category"] == "adversarial"):
        print("FAIL: adversarial cases must all pass")
        failed = True
    if BASELINE.exists() and not args.category:
        base = json.loads(BASELINE.read_text())
        if summary["pass_rate"] < base["pass_rate"]:
            print(f"FAIL: pass rate {summary['pass_rate']} < baseline {base['pass_rate']}")
            failed = True
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
