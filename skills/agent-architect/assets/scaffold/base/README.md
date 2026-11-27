# {{name}}

A Claude-powered **{{pattern}}** scaffolded by agent-architect. Model: `{{model}}`.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # add ANTHROPIC_API_KEY (a low-scope dev key)
pytest -q                   # guard + output tests, no API calls
python -m agent.main "your task"
```

## Before this is real

The example tool (`lookup_record` over a fake dict), schema, workers and every case in `evals/cases.yaml` are **placeholders**. They are marked in the code and `audit.py` fails (rule V4) until each is replaced with task-specific behaviour.

## What's built in

| Concern | Where |
|---|---|
| Model pin, transient-only retries, request-id logging, token ledger | `agent/core/client.py` |
| Turn + budget caps | `agent/core/config.py` (`MAX_TURNS`, `MAX_BUDGET_USD`) |
| PreToolUse guard (destructive commands, protected paths, secrets, approvals) | `agent/core/guards.py`, `.claude/hooks/guard.py` |
| stop_reason handling, structured output, validate → re-prompt | `agent/core/output.py` |
| Untrusted-content delimiting, PII redaction | `agent/core/guards.py` |
| Frozen evals + regression gate | `evals/` |

## Evals

```bash
python evals/run_evals.py --dry-run         # check cases.yaml
python evals/run_evals.py                   # run (costs API credits)
python evals/run_evals.py --save-baseline   # accept current results
```

## Credits

Built on open-source projects listed in `THIRD_PARTY_NOTICES.md`.
