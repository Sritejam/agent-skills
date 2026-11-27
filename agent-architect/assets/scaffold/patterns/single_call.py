"""Pattern: single call. One structured-output request + semantic validation.

Use for classification, extraction, scoring: anything one request answers.
Replace SCHEMA / validate() / the prompt with your domain.
"""
from __future__ import annotations

import json
import logging
import sys
from typing import Any

from agent.core import Claude, load_prompt, structured, wrap_untrusted

log = logging.getLogger(__name__)

# additionalProperties: false on every object; enums for categories; honest `required`.
SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": ["question", "bug", "feature_request", "other"]},
        "summary": {"type": "string", "description": "One sentence, <= 30 words"},
        "confidence": {"type": "number", "description": "0.0 to 1.0"},
    },
    "required": ["category", "summary", "confidence"],
    "additionalProperties": False,
}


def validate(data: dict[str, Any]) -> list[str]:
    """Rules the schema layer can't enforce (ranges, lengths, cross-field logic)."""
    errors = []
    if not 0.0 <= data.get("confidence", -1) <= 1.0:
        errors.append("confidence must be between 0.0 and 1.0")
    if len(data.get("summary", "").split()) > 30:
        errors.append("summary must be at most 30 words")
    return errors


def run(task: str, *, claude: Claude | None = None) -> str:
    claude = claude or Claude()
    result = structured(
        claude,
        system=load_prompt("system.md"),
        # The task is user-supplied, so it's delimited as data; instructions come after it.
        messages=[{"role": "user", "content": wrap_untrusted("user", task) + "\n\nClassify the input above."}],
        schema=SCHEMA,
        validate=validate,
    )
    log.info("usage %s", claude.ledger.summary())
    return json.dumps(result)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(run(" ".join(sys.argv[1:]) or sys.stdin.read()))
