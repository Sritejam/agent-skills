---
tags: [agent-architect]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Build me a research assistant with the Claude Agent SDK. Given a company name it searches the web, reads that company's 10-K from a local folder ./filings, and writes a one-page markdown brief to ./briefs. Requirements: under $0.50 and 2 minutes per run, it must never write anywhere except ./briefs, and every claim needs a cited source. Example: input "Acme Corp" gives a brief covering revenue, segments and top risks, each with a citation. Use claude-sonnet-5-5. I've answered everything I can, so go ahead.
