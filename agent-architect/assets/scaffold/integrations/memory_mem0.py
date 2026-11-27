"""Long-term per-user memory via mem0 (repo: mem0ai/mem0, install: mem0ai).

Gotchas (verified against the mem0 source):
- Default embedder is OpenAI → set OPENAI_API_KEY, or configure a local embedder
  (see mem0 docs/components/embedders/).
- mem0's Anthropic LLM wrapper always sends `temperature`, which current Claude models
  reject. Use a model that accepts sampling params for mem0's internal LLM
  (MEM0_LLM_MODEL, default claude-haiku-4-5) and verify with a smoke test.
- Recalled memories originated from user content → wrap them as untrusted data.
"""
from __future__ import annotations

import os
from typing import Any

from mem0 import Memory

from agent.core import wrap_untrusted

_CONFIG: dict[str, Any] = {
    "llm": {
        "provider": "anthropic",
        "config": {"model": os.environ.get("MEM0_LLM_MODEL", "claude-haiku-4-5"), "max_tokens": 2000},
    },
}

_memory: Memory | None = None


def _mem() -> Memory:
    global _memory
    if _memory is None:
        _memory = Memory.from_config(_CONFIG)
    return _memory


def remember(messages: list[dict[str, str]], user_id: str) -> None:
    """Store facts from a finished exchange. Pass PII-minimized text (core.guards.redact_pii)."""
    _mem().add(messages, user_id=user_id)


def recall(query: str, user_id: str, top_k: int = 5) -> str:
    """Relevant memories as a delimited untrusted block, ready to append to a user turn."""
    hits = _mem().search(query, top_k=top_k, filters={"user_id": user_id})
    items = [h.get("memory", "") for h in (hits.get("results", []) if isinstance(hits, dict) else hits)]
    return wrap_untrusted("memory", items) if items else ""
