# Guardrails: what every generated agent must satisfy

Each rule has an ID. `scripts/audit.py` checks the ones marked **[auto]**; you check the rest by reading the code. A guardrail that lives only in prompt text is guidance, not a guardrail. Where a rule can be enforced in code (hook, permission, validator, budget), enforce it there.

## Contents
- L: Loop and budget
- E: Errors and retries
- O: Output handling
- C: Context and caching
- S: Security and untrusted input
- T: Tools
- P: Permissions and Claude Code config
- M: Models and versioning
- V: Verification

---

## L: Loop and budget

- **L1 [auto]** Every Agent SDK run sets `max_turns` and `max_budget_usd`. *Why:* a run is uncapped by default; an unbounded loop is a defect, and the model must never be trusted to self-limit.
- **L2 [auto]** Custom loops are `for turn in range(MAX_TURNS)`, never `while True` around an API call.
- **L3** Branch on `ResultMessage.subtype` first; only `success` carries `result`. Handle `error_max_turns`, `error_max_budget_usd`, `error_during_execution` explicitly.
- **L4** Record `total_cost_usd`, `num_turns`, `usage`, `session_id` per run (the scaffold's ledger does this).
- **L5** Parallel fan-out uses a semaphore and `gather(..., return_exceptions=True)` so one failure doesn't cancel the batch and you don't trigger a 429 storm.

## E: Errors and retries

- **E1 [auto]** All Messages API calls go through `agent/core/client.py`. *Why:* model pin, retries, logging and cost accounting live in one place, so a model bump is a one-line change.
- **E2** Retry only what can clear: 429, 500, 504, 529, timeouts, connection errors (the Anthropic SDK does this with backoff; the scaffold sets `max_retries`). Never wrap 400/401/403/404/413 in a retry loop: they fail identically every time and burn budget. 401 is surfaced immediately.
- **E3** Honor `retry-after`; cap attempts so persistent failure fails loudly.
- **E4** Log `request_id` and error `type` on failure; never parse the human `message`.
- **E5** Streaming: a 200 can still carry a late `error` event, so handle it.
- **E6** Return tool failures as `tool_result` with `is_error: true` so Claude can adapt; don't crash the loop.

## O: Output handling

- **O1 [auto]** Read response content by iterating blocks and checking `type`, never `content[0]` (thinking or tool_use blocks may come first).
- **O2** Check `stop_reason` **before** parsing: `end_turn` = trust; `max_tokens` = truncated (raise cap or continue); `refusal` = read `stop_details`, don't retry blindly; `model_context_window_exceeded` = prune/compact; `tool_use` = run tools.
- **O3** Machine-consumed output uses structured outputs (`output_config.format` json_schema, or `output_format` in the Agent SDK) or strict tools, with `additionalProperties: false`, enums for categories, honest `required`.
- **O4** Schema-valid ≠ correct: run **semantic validation** (business rules, ranges, cross-field checks; the schema layer doesn't enforce min/max/length) and re-prompt with the exact error, with a retry cap.
- **O5** Confident tone is not evidence. High-stakes outputs are grounded (cite the provided source), cross-checked, or human-approved before acting: generate → verify → act.

## C: Context and caching

- **C1** System prompt holds stable role/rules only. No per-request data, no timestamps, no UUIDs (they silently break caching).
- **C2** Prune tool output to load-bearing fields before it enters history.
- **C3** Durable facts go in external memory or files, not in the hope that the window will hold them.
- **C4** Subagent tasks contain every fact the subagent needs (it inherits nothing from the parent).
- **C5** Serialize tools/data with stable key order (`sort_keys=True`) where they're part of the cached prefix.

## S: Security and untrusted input

- **S1** Untrusted = anything the app didn't author: user messages, uploads, retrieved docs, web pages, tool results, MCP output.
- **S2 [auto, heuristic]** Untrusted content never goes into the system prompt. Deliver it in `tool_result` blocks or inside labeled, JSON-encoded delimiters (`core.guards.wrap_untrusted`), with your instructions **after** it in the user turn.
- **S3** Defense in depth: input isolation + least privilege + output checks + environment boundary (sandbox, filesystem bounds, egress). Only the environment layer is deterministic, so don't rely on the model to resist injection.
- **S4 [auto]** No secrets in code, prompts, CLAUDE.md or committed files. Keys come from env or a secret store; `.env` is gitignored; `.env.example` has empty values.
- **S5** Minimize PII before it enters the prompt (`core.guards.redact_pii`); keep raw prompts/payloads out of logs; tool args send only the fields the downstream service needs.
- **S6** Multi-user apps: one session/context per user, authorized per action at the system that holds the data. Never reuse a context window across users.
- **S7** Separate dev and prod keys; least-scope keys.

## T: Tools

- **T1** Each tool description covers: what it does, when to use it, when **not** to, and limits/caveats (3–4 sentences). When Claude misroutes, rewrite descriptions first.
- **T2** Few, well-scoped, distinctly named tools, namespaced across systems (`billing_list_invoices`). Consolidate CRUD on one resource behind an `action` parameter rather than one tool per endpoint.
- **T3** `required` only for fields with no safe default. Enums for fixed sets. `strict: true` where argument shape matters.
- **T4** Read-only tools can run concurrently; state-changing tools run sequentially.
- **T5** High-impact tools (delete, send, pay, deploy, change access) are gated in code: PreToolUse hook `deny` / `ask`, or a human-approval step **before** execution, never a log after.

## P: Permissions and Claude Code config

- **P1 [auto]** Never `permission_mode="bypassPermissions"`. Headless/CI uses `dontAsk` with an explicit `allowed_tools` list.
- **P2 [auto]** A PreToolUse guard is registered (`hooks=` in SDK options, and `.claude/settings.json` hooks for dev sessions). PreToolUse is the only point that can stop an action; PostToolUse only observes.
- **P3** `allowed_tools` / `disallowed_tools` / subagent `tools` are least privilege. Omitting `tools` on a subagent gives it everything, so set it.
- **P4 [auto]** `.claude/settings.json` has a `permissions.deny` list; `settings.local.json` and `CLAUDE.local.md` are gitignored.
- **P5 [auto]** `CLAUDE.md` exists and stays under ~200 lines: structure, conventions, exact commands. Rules that must hold go in hooks, not CLAUDE.md.
- **P6** MCP servers: least-scope credentials via env; remote servers use OAuth bearer in the `Authorization` header; local HTTP binds 127.0.0.1.

## M: Models and versioning

- **M1 [auto]** Model IDs are pinned exact strings (no `-latest`), set in one config place.
- **M2 [auto]** No `temperature` / `top_p` / `top_k` on current models.
- **M3** Prompts, schemas, model ID and settings/hooks are versioned together in git; a change to any is reviewed like code and gated by evals.

## V: Verification

- **V1 [auto]** `evals/cases.yaml` exists with representative, boundary **and** adversarial cases.
- **V2** Evals pass before "done"; a new model or prompt version must match or beat the baseline (`evals/baseline.json`).
- **V3** Tests for guards and output parsing run without an API key.
