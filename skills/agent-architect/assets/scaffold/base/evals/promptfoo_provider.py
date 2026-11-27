"""promptfoo Python provider: lets `npx promptfoo eval -c evals/promptfooconfig.yaml` call the agent."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent.main import run  # noqa: E402


def call_api(prompt, options, context):
    try:
        return {"output": run(prompt)}
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}
