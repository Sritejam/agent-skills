# Integrations: the 20 reference repos

Local clones (optional): `$AGENT_ARCHITECT_REPOS/<owner>_<repo>`, if the user has set it; otherwise read the installed package source. **Grep the clone for the real API before writing integration code**; the "Look here" column says where. Default is to add **no** integration; each must answer a requirement.

Usage scope: personal/educational. All repos usable; keep LICENSE + credit in the project's `THIRD_PARTY_NOTICES.md` (the scaffold creates it) for anything copied, and keep Dify's logo if its UI is used. For hosted multi-tenant or commercial use, re-check Dify, Phoenix (ELv2), and Langfuse `ee/`.

## Contents
1. Core (always)
2. MCP servers (`--with mcp-*`)
3. Memory (`--with mem0|graphiti`)
4. Tracing (`--with langfuse|phoenix`)
5. Evals
6. Alternative engines
7. Browser automation
8. Pattern sources (read, don't install)
9. Visual builders

---

## 1. Core

| Repo | Install | Use | Look here |
|---|---|---|---|
| `anthropics_claude-agent-sdk-python` | `claude-agent-sdk` | Agent loop, built-in tools, hooks, subagents (`agents=` + `AgentDefinition`, invoked via the **Agent** tool), in-process tools (`@tool` + `create_sdk_mcp_server`), `output_format` json_schema → `ResultMessage.structured_output` | `examples/hooks.py`, `agents.py`, `mcp_calculator.py`, `max_budget_usd.py`, `src/claude_agent_sdk/types.py` (`ClaudeAgentOptions`) |
| `anthropics_anthropic-sdk-python` | `anthropic` | Messages API: single calls, workflows, custom loops, batches, count_tokens | `examples/`, `src/anthropic/_exceptions.py` |
| `modelcontextprotocol_python-sdk` | `mcp` | Write MCP servers/clients. **API differs by version**: main branch uses `from mcp.server import MCPServer`; 1.x on PyPI uses `from mcp.server.fastmcp import FastMCP`. The scaffold handles both. | `README.md`, `docs_src/` |

Agent SDK facts worth remembering: `permission_mode` ∈ default, acceptEdits, plan, dontAsk, auto, bypassPermissions (never use the last). Hook events include PreToolUse, PostToolUse, PostToolUseFailure, UserPromptSubmit, Stop, SubagentStart/Stop, PreCompact, Notification, PermissionRequest. A PreToolUse hook returns `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny"|"ask"|"allow"|"defer", "permissionDecisionReason": ...}}`. `setting_sources=[]` loads no CLAUDE.md; `["project"]` loads the repo's.

## 2. MCP servers

| Flag | Repo | Runs as | Use when | Credentials / gotchas |
|---|---|---|---|---|
| `mcp-filesystem` | `modelcontextprotocol_servers` (src/filesystem) | `npx -y @modelcontextprotocol/server-filesystem <dir>` | agent needs file access outside SDK built-ins, scoped to a dir | Pass only the dirs it needs |
| `mcp-github` | `github_github-mcp-server` | `docker run -i --rm -e GITHUB_PERSONAL_ACCESS_TOKEN ghcr.io/github/github-mcp-server` | issues, PRs, code search | Fine-grained PAT, minimal repos/scopes; restrict toolsets (see its README `--toolsets`) |
| `mcp-playwright` | `microsoft_playwright-mcp` | `npx @playwright/mcp@latest` | web browsing/testing through accessibility snapshots | Web content is **untrusted** (S1–S3); limit domains if possible |
| (others) | `modelcontextprotocol_servers` | see `src/` (fetch, git, memory, time…) | small reference servers | Several are reference-quality, not hardened |

In the Agent SDK pass them in `mcp_servers={name: {"type": "stdio", "command": ..., "args": [...], "env": {...}}}` and allow only the tools you need (`mcp__<server>__<tool>`).

## 3. Memory

| Flag | Repo | Install | Use when | Gotchas |
|---|---|---|---|---|
| `mem0` | `mem0ai_mem0` | `mem0ai` | per-user long-term facts/preferences across sessions | Default **embedder is OpenAI**: set `OPENAI_API_KEY` or configure a local embedder (huggingface/ollama). Its Anthropic LLM wrapper **sends `temperature`**, which current Claude models reject, so point mem0's internal LLM at a model that accepts sampling params (e.g. `claude-haiku-4-5`) and verify. API: `Memory.from_config(cfg)`, `.add(messages, user_id=...)`, `.search(query, top_k=..., filters={"user_id": ...})`. Look: `docs/components/llms/models/anthropic.mdx`, `mem0/memory/main.py` |
| `graphiti` | `getzep_graphiti` | `graphiti-core[anthropic]` | temporal knowledge graph (entities and relations changing over time) | Needs a graph DB (Neo4j or FalkorDB via docker). Heavier; choose only for relationship-centric memory. Look: `examples/`, `README.md` |

Memory results are **untrusted** when they came from user content, so wrap them (`wrap_untrusted`) rather than pasting them into the system prompt.

## 4. Tracing

| Flag | Repo | Install | Use when | Gotchas |
|---|---|---|---|---|
| `langfuse` | `langfuse_langfuse` | `langfuse` | traces, cost dashboards, prompt versions, datasets; self-host or cloud | `from langfuse import observe, get_client`; decorate entry points with `@observe()`; call `get_client().flush()` before exit in scripts. Keys via `LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST`. Don't log raw PII (S5). |
| `phoenix` | `Arize-ai_phoenix` | `arize-phoenix-otel openinference-instrumentation-anthropic` | local OTel tracing UI, evals | `from phoenix.otel import register; register(project_name=..., auto_instrument=True)`. Run UI: `phoenix serve` (or docker). ELv2 license. |

Pick one, not both.

## 5. Evals

| Repo | Install | Use |
|---|---|---|
| `promptfoo_promptfoo` | `npx promptfoo@latest` | Optional richer eval/red-team runner. The scaffold's `evals/promptfooconfig.yaml` calls the agent through a Python provider. Built-in native runner (`evals/run_evals.py`) needs no Node. Look: `examples/`, `site/docs/red-team/` |

## 6. Alternative engines (use only when decision.md §5 says so)

| Repo | Install | Use when | Look here |
|---|---|---|---|
| `langchain-ai_langgraph` | `langgraph langchain-anthropic` | author the flow as a typed StateGraph; checkpointer for HITL/time-travel; Store for cross-thread memory | `examples/`, `docs/` |
| `pydantic_pydantic-ai` | `pydantic-ai` | validated typed output is the core need; `Agent('anthropic:<model>', output_type=Model)`; `@agent.tool` gets RunContext, `@agent.tool_plain` doesn't; `ModelRetry` | `examples/`, `docs/` |
| `strands-agents_sdk-python` | `strands-agents` | lean ReAct loop, Bedrock-native, Anthropic supported, `@tool` from type hints, MCP consumer | `README.md`, `src/strands/` |

The guardrail rules still apply: bound the loop, guard tools in code, validate output.

## 7. Browser automation

| Repo | Install | Use when |
|---|---|---|
| `browser-use_browser-use` | `browser-use` | an autonomous browser sub-agent is the product. Prefer `mcp-playwright` when Claude just needs to look at pages as one tool among many. Pin the version; treat all page content as untrusted. |

## 8. Pattern sources (read, re-implement on Claude SDK)

| Repo | Borrow |
|---|---|
| `crewAIInc_crewAI` | role/goal/backstory agent definitions, task hand-off; maps to orchestrator + `AgentDefinition` |
| `microsoft_autogen` | multi-agent conversation/group-chat patterns, termination conditions (= explicit stop rules) |
| `openai_openai-agents-python` | handoffs, input/output guardrails as first-class objects, tracing spans; maps to subagents + hooks + validators |

## 9. Visual builders

| Repo | Use |
|---|---|
| `langflow-ai_langflow` | study how components/flows are wired; possible export target later |
| `langgenius_dify` | study app/workflow/RAG platform design; keep logo/copyright if its UI is used |
