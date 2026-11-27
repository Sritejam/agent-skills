"""Output-handling tests with a fake client: no API key needed."""
import json
from types import SimpleNamespace as NS

import pytest

from agent.core import Claude, structured, text_of
from agent.core.output import ContextFull, OutputError, Refused, Truncated

SCHEMA = {"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"],
          "additionalProperties": False}


def resp(text, stop="end_turn", blocks=None):
    content = blocks if blocks is not None else [NS(type="text", text=text)]
    return NS(content=content, stop_reason=stop, stop_details=None,
              usage=NS(input_tokens=10, output_tokens=5, cache_creation_input_tokens=0, cache_read_input_tokens=0))


class FakeMessages:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def create(self, **params):
        self.calls.append(params)
        return self.replies.pop(0)


def fake_claude(*replies):
    client = NS(messages=FakeMessages(replies))
    return Claude(model="claude-test", client=client), client.messages


def test_text_of_skips_non_text_blocks():
    r = resp("", blocks=[NS(type="thinking", thinking="..."), NS(type="text", text="hi")])
    assert text_of(r) == "hi"


def test_structured_success_sets_schema():
    claude, msgs = fake_claude(resp(json.dumps({"n": 3})))
    assert structured(claude, messages=[{"role": "user", "content": "x"}], schema=SCHEMA) == {"n": 3}
    assert msgs.calls[0]["output_config"]["format"]["schema"] == SCHEMA


def test_structured_reprompts_on_semantic_error():
    claude, msgs = fake_claude(resp(json.dumps({"n": -1})), resp(json.dumps({"n": 2})))
    out = structured(claude, messages=[{"role": "user", "content": "x"}], schema=SCHEMA,
                     validate=lambda d: [] if d["n"] >= 0 else ["n must be >= 0"])
    assert out == {"n": 2}
    assert "n must be >= 0" in msgs.calls[1]["messages"][-1]["content"]


def test_structured_gives_up_after_cap():
    claude, _ = fake_claude(*[resp("not json")] * 3)
    with pytest.raises(OutputError):
        structured(claude, messages=[{"role": "user", "content": "x"}], schema=SCHEMA, max_retries=2)


@pytest.mark.parametrize("stop,exc", [("max_tokens", Truncated), ("refusal", Refused),
                                      ("model_context_window_exceeded", ContextFull)])
def test_stop_reasons_raise_before_parsing(stop, exc):
    claude, _ = fake_claude(resp('{"n": 1', stop=stop))
    with pytest.raises(exc):
        structured(claude, messages=[{"role": "user", "content": "x"}], schema=SCHEMA)


@pytest.mark.parametrize("param", ["temperature", "top_p", "top_k"])
def test_sampling_params_rejected(param):
    claude, _ = fake_claude(resp("x"))
    with pytest.raises(ValueError):
        claude.create(messages=[{"role": "user", "content": "x"}], **{param: 0.5})


def test_ledger_counts_cache_in_prompt_tokens():
    claude, _ = fake_claude(resp("x"))
    claude.create(messages=[{"role": "user", "content": "x"}])
    assert claude.ledger.calls == 1 and claude.ledger.prompt_tokens == 10
