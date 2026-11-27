# Stage 1: Interview

Aim: turn an idea into a contract a developer can build and QA can verify. Move left to right:

**business need** (the outcome, in plain words) → **functional requirements** (input → expected output) → **acceptance criteria** (conditions that prove it works)

Ask in batches of 3–4. Skip what the user already answered. Offer concrete options so they can click instead of writing essays.

## Batch 1: What and why

1. What should the agent accomplish, and for whom? (One sentence outcome, not features.)
2. Walk me through **one real example**: what goes in, what should come out?
3. What does it do today without the agent (manual process, script, nothing)?
4. What would make you say "this works"? (Becomes acceptance criteria.)

## Batch 2: Inputs, outputs, actions

5. Input sources: user chat, files, URLs, APIs, databases, repos, email…?
6. Output shape: free text, JSON for another system, files, a PR, a message sent somewhere?
7. **Actions with side effects**: does it write, delete, send, pay, deploy, change access? (Each one needs a guard and maybe human approval.)
8. Systems it must reach: public web, private APIs, internal DBs, GitHub, local files?

## Batch 3: Constraints (the four budgets)

9. **Latency**: interactive (seconds, needs streaming) or background (minutes/hours OK, batch possible)?
10. **Volume**: runs per day? (Drives caching, batching, model tier.)
11. **Cost ceiling**: per run or per month?
12. **Data sensitivity**: PII, secrets, regulated data, data residency? Multi-user (needs per-user isolation)?

## Batch 4: Risk and operations

13. Cost of a wrong answer or wrong action: annoying, expensive, or catastrophic/irreversible?
14. Who runs it: you interactively, a cron/CI job (headless), or end users?
15. Anything it must **never** do?
16. More examples, especially tricky or edge cases and anything adversarial (hostile input, injection attempts)?

## Things to listen for

- **Infrastructure in disguise**: "must answer in 2s", "must stay in EU", "10k/day" are architecture constraints, not prompt features.
- **Feelings to translate**: "fast", "smart", "reliable", "safe" each need a number or a rule.
- **Hidden agents**: "it should figure out…" with an unknown number of steps is a real agent signal; "it does A then B then C" is a workflow.
- **Hidden side effects**: "and then it updates the ticket" is a write action that needs a guard.

## Requirements template (`design/requirements.md`)

```markdown
# <Agent name>: Requirements

## Business need
<one paragraph, outcome-first>

## Users and environment
- Who runs it: <interactive | headless/CI | end users>
- Multi-user: <yes/no> → per-user session isolation <required/not>

## Functional requirements
| # | Input | Expected behavior / output |
|---|---|---|
| F1 | ... | ... |

## Acceptance criteria
- [ ] AC1: <measurable condition>

## Side-effecting actions
| Action | System | Reversible? | Guard | Human approval? |
|---|---|---|---|---|

## Budgets
- Latency: <p95 target, streaming yes/no>
- Volume: <runs/day>
- Cost: <ceiling>
- Data: <sensitivity, residency, PII handling>

## Must never
- ...

## Examples (seed eval set)
| Category | Input | Expected |
|---|---|---|
| representative | ... | ... |
| boundary | ... | ... |
| adversarial | ... | ... |

## Decisions and overrides
- <e.g. "User chose full agent despite workflow recommendation because …">
```
