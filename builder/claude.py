"""One-shot Claude calls through the Claude Agent SDK (works with a Claude login or ANTHROPIC_API_KEY).
Every call is written to the trace: model, one-line purpose, seconds, cost."""
import asyncio
import json
import os
import re
import tempfile
import time

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

_SCRATCH = tempfile.mkdtemp(prefix="builder-claude-")
MODEL = os.environ.get("BUILDER_MODEL", "claude-opus-5-5")


async def _ask(prompt, system, model, effort):
    # No tools are allowed; a few turns of headroom so a refused tool attempt does not end the call in an error.
    # tools=[] removes every built-in tool (allowed_tools=[] only means "none pre-approved"); the call runs in an
    # empty scratch folder, not in the repository that holds env.sh, and without MCP servers or skills.
    opts = ClaudeAgentOptions(model=model, system_prompt=system, allowed_tools=[], tools=[], max_turns=4,
                              permission_mode="dontAsk", setting_sources=[], effort=effort,
                              cwd=_SCRATCH, strict_mcp_config=True)
    turns, cost = [], 0.0
    try:
        async for m in query(prompt=prompt, options=opts):
            if isinstance(m, AssistantMessage):
                t = "".join(b.text for b in m.content if isinstance(b, TextBlock))
                if t.strip():
                    turns.append(t)
            elif isinstance(m, ResultMessage):
                cost = m.total_cost_usd or 0.0
                if m.result and not turns:
                    turns = [m.result]
    except Exception:
        if not turns:
            raise
    # the answer is the longest text turn (a short preamble or a refused-tool remark is not the answer)
    return (max(turns, key=len) if turns else ""), cost


def ask(prompt, system, purpose, trace, model=MODEL, effort="high"):
    t0 = time.time()
    try:
        out, cost = asyncio.run(_ask(prompt, system, model, effort))
    except Exception as e:                    # one retry: a transient API or SDK error must not stop the build
        trace.note(f"model call failed ({type(e).__name__}: {str(e)[:200]}); retrying once")
        out, cost = asyncio.run(_ask(prompt, system, model, effort))
    trace.model_call(model, purpose, time.time() - t0, cost)
    return out


def ask_many(jobs, trace, model=MODEL, effort="high"):
    """jobs: list of (prompt, system, purpose). Runs them concurrently."""
    async def one(p, s):
        try:
            return await _ask(p, s, model, effort)
        except Exception as e:
            trace.note(f"model call failed ({type(e).__name__}: {str(e)[:200]}); retrying once")
            try:
                return await _ask(p, s, model, effort)
            except Exception as e2:
                trace.note(f"model call failed again ({type(e2).__name__}); continuing without it")
                return "", 0.0

    async def run():
        t0 = time.time()
        res = await asyncio.gather(*[one(p, s) for p, s, _ in jobs])
        for (p, s, purpose), (_, cost) in zip(jobs, res):
            trace.model_call(model, purpose, time.time() - t0, cost)
        return [r[0] for r in res]
    return asyncio.run(run())


def json_block(text, keys=None):
    """The spec object in a model answer. Each ```json fence is parsed on its own (an answer may quote small JSON
    values before the final spec); without fences, objects are scanned with raw_decode. Prefers objects holding
    all `keys`, then the largest."""
    cands = []
    for m in re.finditer(r"```(?:json)?\s*(.*?)```", text, re.S):
        try:
            v = json.loads(m.group(1))
        except Exception:
            continue
        if isinstance(v, dict):
            cands.append(v)
    if not cands:
        dec, i = json.JSONDecoder(), text.find("{")
        while i != -1:
            try:
                v, end = dec.raw_decode(text, i)
            except Exception:
                i = text.find("{", i + 1)
                continue
            if isinstance(v, dict):
                cands.append(v)
            i = text.find("{", end)
    if not cands:
        raise ValueError("no JSON object in the answer")
    if keys:
        cands = [c for c in cands if all(k in c for k in keys)] or cands
    return max(cands, key=lambda c: len(json.dumps(c)))
