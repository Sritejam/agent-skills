# agent-skills

Claude Code skills for building AI agents.

## agent-architect

An interactive builder for agents, with a tested scaffold currently focused on Claude-powered Python projects. The workflow can plan other stacks, but it must label them as recipes or experimental until their scaffolds and checks are implemented and tested.

1. **Interview**: turns your idea into requirements, with examples that become the eval set
2. **Decide**: single call vs workflow vs agent (pushes back when you don't need an agent)
3. **Architect**: pattern, model for each step, tools/MCP/skills, integrations. **Approval gate**
4. **Scaffold**: generates a project from a vetted template (6 patterns, optional mem0 / graphiti / langfuse / phoenix / MCP presets)
5. **Verify**: static audit + tests + evals (representative, boundary, adversarial). **Done gate**
6. **Hand off**: how to run it, guardrails, scores, cost, open risks

The scaffold includes runtime-specific templates, guardrails, tests, and starter evals. Messages API patterns use the shared client; Agent SDK patterns use the SDK runtime directly. Replace demo tools and starter evals with requirement-specific implementations before treating a generated project as complete. See [the portability and support guide](agent-architect/references/portability.md) for stack maturity, architecture decisions, and end-to-end verification gates.

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
