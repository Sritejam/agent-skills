"""Support bot: answers customer questions using our docs."""
import json

import anthropic
from claude_agent_sdk import ClaudeAgentOptions

client = anthropic.Anthropic()
MODEL = "claude-3-5-sonnet-latest"


def answer(question: str) -> dict:
    messages = [{"role": "user", "content": question}]
    while True:
        resp = client.messages.create(model=MODEL, max_tokens=1024, temperature=0.7,
                                      system=f"You are a support bot. Question: {question}",
                                      messages=messages)
        if resp.content[0].type == "text":
            return json.loads(resp.content[0].text)


def sdk_options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(model=MODEL, permission_mode="bypassPermissions")
