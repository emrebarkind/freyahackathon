"""Build the Builder — brief in, tested Freya agent out.

  python -m builder build briefs/sample_collections_brief.md            # local loop only
  python -m builder build <brief> --runner freya --deploy               # test on real Freya agent
  python -m builder freya-check                                         # verify API key / workspace
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import random
import time
from functools import partial
from pathlib import Path

from . import stages
from .spec import AgentDraft


def load_env(path: str = ".env") -> None:
    p = Path(path)
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                if v.strip():
                    os.environ.setdefault(k.strip(), v.strip())


def read_brief(path: str) -> str:
    p = Path(path)
    files = sorted(x for x in p.rglob("*") if x.is_file()) if p.is_dir() else [p]
    return "\n\n".join(f"=== {f.name} ===\n{f.read_text(errors='ignore')}" for f in files)


def freya_config(freya, draft: AgentDraft, base: dict | None) -> dict:
    cfg = copy.deepcopy(base) if base else freya.agent_defaults()["config"]
    llm_cfg = cfg["llmConfig"]
    llm_cfg["systemPrompt"] = draft.system_prompt
    llm_cfg["firstMessage"] = draft.first_message
    llm_cfg["firstMessageMode"] = "assistant-speaks-first"
    llm_cfg["farewellMessage"] = draft.farewell_message
    llm_cfg["temperature"] = 0.2
    return cfg


def deploy(freya, draft: AgentDraft, agent_id: str | None, base_cfg: dict | None, language: str | None) -> str:
    cfg = freya_config(freya, draft, base_cfg)
    if agent_id:
        freya.update_agent(agent_id, name=draft.name, config=cfg)
        return agent_id
    res = freya.create_agent(draft.name, cfg, language=language)
    return res["agent"]["id"]


def score(results) -> float:
    return sum(r.verdict.passed for r in results) / max(1, len(results))


def cmd_build(a) -> None:
    out = Path("runs") / time.strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    save = lambda name, obj: (out / name).write_text(obj if isinstance(obj, str) else json.dumps(obj, indent=2, ensure_ascii=False))

    brief = read_brief(a.brief)
    print("[1/5] extracting policy ...")
    policy = stages.extract_policy(brief)
    save("policy.json", policy.model_dump())
    print(f"      {len(policy.rules)} rules, {len(policy.outcomes)} outcomes, {len(policy.ambiguities)} ambiguities")

    print("[2/5] generating scenarios ...")
    scenarios = stages.generate_scenarios(policy, a.scenarios)
    save("scenarios.json", [s.model_dump() for s in scenarios])
    random.Random(0).shuffle(scenarios)
    cut = max(1, int(len(scenarios) * 0.7))
    train, hold = scenarios[:cut], scenarios[cut:]
    by_id = {s.id: s for s in scenarios}

    print("[3/5] compiling agent ...")
    platform_notes = Path(a.platform_notes).read_text() if a.platform_notes else ""
    draft = stages.compile_agent(policy, platform_notes)
    save("agent_v0.json", draft.model_dump())

    freya = agent_id = base_cfg = None
    if a.runner == "freya" or a.deploy:
        from .freya import Freya
        freya = Freya()
        base_cfg = freya.get_agent(a.agent_id)["config"] if a.agent_id else None
        agent_id = a.agent_id

    def make_runner(d: AgentDraft):
        nonlocal agent_id
        if a.runner == "freya":
            agent_id = deploy(freya, d, agent_id, base_cfg, policy.language)
            return lambda dd, s: stages.run_freya_case(freya, agent_id, dd, s)
        return partial(stages.run_local_case, agent_model=a.agent_model)

    best, best_score = draft, -1.0
    for it in range(a.iterations + 1):
        print(f"[4/5] iteration {it}: evaluating on {len(train)} train cases ...")
        res = stages.evaluate(policy, draft, train, make_runner(draft))
        sc = score(res)
        save(f"results_v{it}.json", [r.model_dump() for r in res])
        print(f"      train pass rate {sc:.0%}")
        if sc > best_score:
            best, best_score = draft, sc
        if sc == 1.0 or it == a.iterations:
            break
        print("      optimising prompt ...")
        draft = stages.optimise(policy, best, res, by_id)
        save(f"agent_v{it + 1}.json", draft.model_dump())
        print("      " + draft.changelog.replace("\n", "\n      ")[:800])

    print(f"[5/5] holdout check on {len(hold)} unseen cases (best train {best_score:.0%}) ...")
    hres = stages.evaluate(policy, best, hold, make_runner(best))
    save("results_holdout.json", [r.model_dump() for r in hres])
    save("agent_best.json", best.model_dump())
    save("system_prompt.md", best.system_prompt)
    print(f"      holdout pass rate {score(hres):.0%}")

    if a.deploy:
        agent_id = deploy(freya, best, agent_id, base_cfg, policy.language)
        print(f"deployed Freya agent: {agent_id}")
    print(f"artifacts: {out}")


def cmd_freya_check(_a) -> None:
    from .freya import Freya
    f = Freya()
    print("key:", json.dumps(f.check_key(), indent=1)[:1500])
    print("workspaces:", json.dumps(f.workspaces(), indent=1)[:1500])
    if f.workspace_id:
        print("defaults:", json.dumps(f.agent_defaults(), indent=1)[:3000])


def main() -> None:
    load_env()
    p = argparse.ArgumentParser(prog="builder")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("brief", help="brief file or directory")
    b.add_argument("--scenarios", type=int, default=24)
    b.add_argument("--iterations", type=int, default=3)
    b.add_argument("--runner", choices=["local", "freya"], default="local")
    b.add_argument("--agent-model", default="claude-haiku-5-5", help="local stand-in for the Freya runtime LLM")
    b.add_argument("--agent-id", help="update this existing Freya agent instead of creating one")
    b.add_argument("--platform-notes", help="file with starter-kit specifics (tools, outcome mechanism)")
    b.add_argument("--deploy", action="store_true")
    b.set_defaults(fn=cmd_build)
    c = sub.add_parser("freya-check")
    c.set_defaults(fn=cmd_freya_check)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
