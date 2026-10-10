"""One-shot Claude calls through the Claude Agent SDK (works with a Claude login or ANTHROPIC_API_KEY).
Every call is written to the trace: model, one-line purpose, seconds, cost."""
import asyncio
import json
import os
import re
import time

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

MODEL = os.environ.get("BUILDER_MODEL", "claude-opus-5-5")


async def _ask(prompt, system, model, effort):
    opts = ClaudeAgentOptions(model=model, system_prompt=system, allowed_tools=[], max_turns=1,
                              permission_mode="dontAsk", setting_sources=[], effort=effort)
    text, cost = [], 0.0
    async for m in query(prompt=prompt, options=opts):
        if isinstance(m, AssistantMessage):
            text += [b.text for b in m.content if isinstance(b, TextBlock)]
        elif isinstance(m, ResultMessage):
            cost = m.total_cost_usd or 0.0
            if m.result and not text:
                text = [m.result]
    return "".join(text), cost


def ask(prompt, system, purpose, trace, model=MODEL, effort="high"):
    t0 = time.time()
    out, cost = asyncio.run(_ask(prompt, system, model, effort))
    trace.model_call(model, purpose, time.time() - t0, cost)
    return out


def ask_many(jobs, trace, model=MODEL, effort="high"):
    """jobs: list of (prompt, system, purpose). Runs them concurrently."""
    async def run():
        t0 = time.time()
        res = await asyncio.gather(*[_ask(p, s, model, effort) for p, s, _ in jobs])
        for (p, s, purpose), (_, cost) in zip(jobs, res):
            trace.model_call(model, purpose, time.time() - t0, cost)
        return [r[0] for r in res]
    return asyncio.run(run())


def json_block(text):
    """Extract the JSON object from a model answer (```json fences or the outermost braces)."""
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    raw = m.group(1) if m else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(raw)
