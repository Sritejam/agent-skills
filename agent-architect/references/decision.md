# Stages 2–3: Decisions

## Contents
1. Tier decision (single call / workflow / agent)
2. Pattern catalog → scaffold pattern
3. Model selection
4. Tool mechanism: built-in vs custom vs MCP vs skill
5. Engine choice (Agent SDK vs raw API vs LangGraph/PydanticAI/Strands)
6. Delivery mode and cost levers

---

## 1. Tier decision

| Tier | Who decides the next step | Use when |
|---|---|---|
| **Single call** | nobody: one request | classify, extract, summarize, answer with given context |
| **Workflow** | your code, at design time | steps are known: chain, route, parallelize |
| **Agent** | the model, at run time | open-ended, unknown step count, model should pick tools |
| **Hybrid** | code, with one scoped agent stage | mostly fixed pipeline with one open-ended part (most common good answer) |

Tool use doesn't make something an agent; **who owns the next decision** does.

**Commit to an agent only if all four checks pass:**

| Check | Question | Fails if |
|---|---|---|
| Complexity | Truly multi-step, hard to script? | You can write the steps down |
| Value | Worth higher latency + token cost? | Cheap workflow gets 90% there |
| Viability | Can Claude actually do the open-ended part? | Needs knowledge/access it can't get |
| Cost of error | Is a wrong step recoverable? | Irreversible actions with no approval gate |

Any weak check → drop a tier. Signals for an agent (want more than one): open-ended space you can't enumerate, unknown number of steps, value in the model choosing tools.

Agent costs to state to the user: sequential calls mean they wait longer; every turn re-sends the growing context, so the bill climbs (big tool outputs are the main driver); and errors compound, since a wrong early step becomes "fact" for later steps.

## 2. Pattern catalog

| Pattern | `--pattern` | Shape | Pick when |
|---|---|---|---|
| Single call | `single_call` | one structured-output call + validate/re-prompt | classification, extraction, scoring |
| Prompt chain | `workflow` | A → B → C, each output feeds next | fixed sequence, want inspectable steps, draft→review→refine |
| Router | `workflow` | cheap classifier picks a branch | distinct input types need different handling/models |
| Parallel | `workflow` | fan-out with semaphore, gather, aggregate | independent subtasks, voting, multi-aspect review |
| Agent (SDK) | `sdk_agent` | Claude Agent SDK loop + hooks + budgets | open-ended tasks; you want built-in tools, sessions, subagents |
| Agent (custom loop) | `custom_loop` | hand-rolled Messages API tool loop | you must own tool execution, retries, logging, or run outside the SDK's CLI runtime |
| Orchestrator-workers | `orchestrator` | manager decomposes, delegates to scoped subagents, synthesizes | subtasks decided at run time, need context isolation or tool restriction per worker |
| MCP server | `mcp_server` | expose tools/resources to many clients | capability reused across clients or teams |

Orchestrator vs parallel: in parallel, **code** splits the work ahead of time; in orchestrator, **the manager model** decides subtasks at run time.

Subagent rules (orchestrator): each starts with a fresh context and sees nothing of the parent, so pass every fact it needs in the task. Only its final message returns. Validate it before synthesis. Least-privilege tools per subagent. Delegate high-noise, independent, or blast-radius-contained work; keep quick lookups inline.

## 3. Model selection

Pin exact IDs. Current family (verify against the claude-api skill or docs if unsure):

| Tier | ID | Use for |
|---|---|---|
| Opus | `claude-opus-5-5` | hard reasoning, multi-step coding, long-running agents, orchestrators |
| Sonnet | `claude-sonnet-5-5` | balanced default for high-volume production steps |
| Haiku | `claude-haiku-5-5` | routing, classification, extraction, lightweight subagents |
| Fable | `claude-fable-5-2` | the very hardest, longest work; slowest and priciest |

Mix tiers per step (Haiku routes, Sonnet drafts, Opus handles escalations) instead of sizing everything to the hardest step. Tune `effort` (low/medium/high/xhigh/max) before switching up a tier.

Current-model breaking rules:
- No `temperature` / `top_p` / `top_k`: they return 400. Steer with prompting + effort.
- No assistant prefill to force format: use structured outputs.
- Thinking is `{"type": "adaptive"}`; legacy `budget_tokens` returns 400 on current models.
- Pass thinking blocks back unchanged in tool loops.
- Re-baseline token estimates when switching models (tokenizers differ).

## 4. Tool mechanism: pick the lightest that works

1. **Built-in/server tool** (web_search, web_fetch, code_execution, tool_search): if Anthropic already hosts it, use it and stop. Can't reach private systems.
2. **Custom tool**: specific to this one app, reaches anything your code can. Default for app-specific capabilities.
3. **Skill**: reusable *procedure* (how to do X, in what order) loaded on demand.
4. **MCP server**: reusable *system access* shared across clients/teams.

An MCP server where a custom tool fits is overbuilding. Skills and MCP complement each other: MCP brings reach, the skill brings method.

## 5. Engine choice

Support levels: **Scaffolded** = `scaffold.py` generates it, the audit understands it, and the generated tests pass offline. **Recipe** = guidance and API pointers only: no template, no adapter, no tests; you write the integration by hand and the audit checks it only partially. **Unsupported** = no code is generated for it (see `portability.md` for all four levels, including Experimental).

| Engine | Choose when | Support | Scaffold |
|---|---|---|---|
| **Claude Agent SDK** (default for agents) | want Claude Code's tools, loop, sessions, subagents, hooks, permission modes | Scaffolded | `sdk_agent`, `orchestrator` |
| **Anthropic SDK / Messages API** | single calls, workflows, custom loops, batches | Scaffolded | `single_call`, `workflow`, `custom_loop` |
| **MCP server** (Python `mcp` SDK) | exposing tools to other clients | Scaffolded | `mcp_server` |
| **LangGraph** | you want to *author* the flow as a typed graph with checkpoints, human-in-the-loop, time travel | Recipe | none: start from `workflow`, see integrations.md |
| **PydanticAI** | model-driven agent whose key need is **type-safe validated output** | Recipe | none: see integrations.md |
| **Strands** | lean model-driven loop, AWS/Bedrock-native, MCP consumer | Recipe | none: see integrations.md |
| Non-Claude providers (OpenAI, Gemini, local models) | | Unsupported | none |

When you recommend a Recipe engine, say so plainly in the architecture doc: the user gets the safe core's *ideas* but must hand-port the guards, budget caps and output validation, and the Stage 5 audit will miss engine-specific flaws.

Don't cross-attribute: StateGraph/reducers/checkpointers are LangGraph; validated typed output is PydanticAI's signature. All three work with Claude.

## 6. Delivery and cost levers

- **Sync** (simple, full latency felt) / **streaming** (perceived latency, long outputs) / **batch** (50% off, async, ≤24h, match results by `custom_id`, never by position).
- **Prompt caching**: stable prefix (tools → system → early messages), ≤4 breakpoints, volatile data after the last one. Reads 0.1×, 5-min writes 1.25×, 1-h writes 2×. Silent invalidators: timestamps/UUIDs in system prompt, unstable JSON key order, changing tool set, switching models. Prefix must clear the model's minimum size.
- **Right-size the model** per step.
- **Prune tool output** before it lands in history (biggest single context win).
- Latency budget = worst acceptable response − your own overhead. A tight budget rules out multi-step loops and huge contexts.
