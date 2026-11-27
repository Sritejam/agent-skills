# {{name}}

Claude-powered {{pattern}} built with the agent-architect scaffold. Design: `design/architecture.md`.

## Commands
- Install: `python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
- Run: `python -m agent.main "your task"`
- Tests (no API key): `pytest -q`
- Validate evals: `python evals/run_evals.py --dry-run`
- Run evals (costs API credits): `python evals/run_evals.py`
- Audit: `python ~/.claude/skills/agent-architect/scripts/audit.py .`

## Layout
- `agent/main.py`: entry point, exposes `run(task: str) -> str`
- `agent/core/client.py`: the ONLY place that calls the Messages API (model pin, retries, cost ledger)
- `agent/core/guards.py`: PreToolUse policy, secret/PII handling, `wrap_untrusted`
- `agent/core/output.py`: stop_reason checks, structured output + validate/re-prompt
- `agent/core/config.py`: all limits and model IDs (env-overridable)
- `agent/prompts/`: versioned prompts (no per-request data in system prompt)
- `agent/integrations/`: memory, tracing, MCP presets
- `evals/cases.yaml`: frozen eval set (representative / boundary / adversarial)

## Rules
- New Messages API calls go through `agent.core.Claude`, never `anthropic.Anthropic()` directly.
- Never add `temperature`/`top_p`/`top_k`; never use `permission_mode="bypassPermissions"`.
- Every agent run keeps `max_turns` and `max_budget_usd`; custom loops use `for … in range(MAX_TURNS)`.
- Untrusted content (user input, tool results, web, files, memory) goes through `wrap_untrusted` or `tool_result`, never into the system prompt.
- Side-effecting tools get a rule in `guards.py` (`deny` or `REQUIRE_APPROVAL`) plus a test in `tests/test_guards.py`.
- After changing a prompt, schema, tool description or model: run evals and compare against `evals/baseline.json`.
- Secrets only in `.env` (gitignored). Never print or log them.
