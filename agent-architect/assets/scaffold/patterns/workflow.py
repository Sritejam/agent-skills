"""Pattern: workflow. Control flow is fixed in code at design time.

Three building blocks, combine as needed:
  route()     cheap model classifies → pick a branch
  chain()     step outputs feed the next step (draft → review → refine)
  parallel()  independent subtasks, bounded concurrency, failures isolated
Delete the blocks you don't use.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any, Awaitable, Callable

from agent.core import Claude, load_prompt, settings, structured, text_of, check_stop, wrap_untrusted

log = logging.getLogger(__name__)


def ask(claude: Claude, prompt: str, *, model: str | None = None, system: str | None = None) -> str:
    resp = claude.create(model=model, system=system, messages=[{"role": "user", "content": prompt}])
    check_stop(resp)
    return text_of(resp)


# ------------------------------------------------------------------ route

ROUTES = ["simple", "complex"]


def route(claude: Claude, task: str) -> str:
    data = structured(
        claude,
        model=settings.fast_model,  # routing is a Haiku-class job
        messages=[{"role": "user", "content": wrap_untrusted("user", task)
                   + "\n\nIs this request simple (one short answer) or complex (needs analysis)?"}],
        schema={
            "type": "object",
            "properties": {"route": {"type": "string", "enum": ROUTES}},
            "required": ["route"],
            "additionalProperties": False,
        },
    )
    return data["route"]


# ------------------------------------------------------------------ chain

def chain(claude: Claude, task: str) -> str:
    system = load_prompt("system.md")
    draft = ask(claude, wrap_untrusted("user", task) + "\n\nWrite a first draft answer.", system=system)
    review = ask(claude, f"<draft>\n{draft}\n</draft>\n\nList concrete errors or gaps in this draft. "
                         "Reply 'NONE' if there are none.", system=system)
    if review.strip().upper() == "NONE":
        return draft
    return ask(claude, f"<draft>\n{draft}\n</draft>\n<review>\n{review}\n</review>\n\n"
                       "Rewrite the draft fixing every review point. Output only the final answer.",
               system=system)


# ------------------------------------------------------------------ parallel

async def parallel(items: list[Any], fn: Callable[[Any], Awaitable[Any]]) -> list[Any]:
    """Bounded fan-out: a semaphore prevents 429 storms; return_exceptions isolates failures."""
    sem = asyncio.Semaphore(settings.max_concurrency)

    async def guarded(item: Any) -> Any:
        async with sem:
            return await fn(item)

    results = await asyncio.gather(*(guarded(i) for i in items), return_exceptions=True)
    for item, r in zip(items, results):
        if isinstance(r, Exception):
            log.warning("parallel item failed item=%r error=%s", item, type(r).__name__)
    return results


# ------------------------------------------------------------------ entry point

def run(task: str, *, claude: Claude | None = None) -> str:
    claude = claude or Claude()
    branch = route(claude, task)
    log.info("route=%s", branch)
    if branch == "simple":
        out = ask(claude, wrap_untrusted("user", task) + "\n\nAnswer briefly.",
                  model=settings.fast_model, system=load_prompt("system.md"))
    else:
        out = chain(claude, task)
    log.info("usage %s", claude.ledger.summary())
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(run(" ".join(sys.argv[1:]) or sys.stdin.read()))
