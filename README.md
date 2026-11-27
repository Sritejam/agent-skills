# agent-skills

Claude Code skills for building AI agents.

## agent-architect

An interactive, end-to-end builder for Claude-powered agents in Python, with guardrails built in.

1. **Interview**: turns your idea into requirements, with examples that become the eval set
2. **Decide**: single call vs workflow vs agent (pushes back when you don't need an agent)
3. **Architect**: pattern, model for each step, tools/MCP/skills, integrations. **Approval gate**
4. **Scaffold**: generates a project from a vetted template (6 patterns, optional mem0 / graphiti / langfuse / phoenix / MCP presets)
5. **Verify**: static audit + tests + evals (representative, boundary, adversarial). **Done gate**
6. **Hand off**: how to run it, guardrails, scores, cost, open risks

Every generated project includes: a single API client module (pinned model, transient-only retries, token ledger), turn and budget caps, a PreToolUse guard (destructive commands, protected paths, secret leaks, approval for risky tools), stop_reason-aware structured output with validate → re-prompt, untrusted-input delimiting, Claude Code config, and a frozen eval set with a regression gate.

### Install

```bash
git clone https://github.com/Sritejam/agent-skills
cp -r agent-skills/agent-architect ~/.claude/skills/
```

Then in Claude Code, describe what you want ("I want an agent that triages GitHub issues…") or run `/agent-architect`.

Optional: clone the referenced repos locally and set `AGENT_ARCHITECT_REPOS` to that folder (default `~/Desktop/agents/repos`). The skill checks library APIs against them before writing code.

### Scripts

```bash
python agent-architect/scripts/scaffold.py --name my-agent --dest ~/code --pattern sdk_agent --model claude-sonnet-5-5
python agent-architect/scripts/audit.py ~/code/my-agent   # exits 1 on errors
```

## Credits

Inspired by:
- **Jacob Bushong**: *Claude Certified Developer Foundations (CCDV-F)* certification prep course (Udemy / [certmasterclass.com](https://certmasterclass.com/certification/claude-certified-developer-foundations)), covering all 8 domains: agents and workflows, applications and integration, and more.
- **neuraldev**: [*90% of Developers Don't Know These 20 AI Agent GitHub Repos*](https://medium.com/@neuraldev/90-of-developers-dont-know-these-20-ai-agent-github-repos-1b43b1882b80) (Medium).

Open-source projects referenced: see [agent-architect/references/credits.md](agent-architect/references/credits.md). This is a personal/educational project.
