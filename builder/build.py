"""Build the Builder -- one command, brief(s) in, tested Freya phone agent out.

    python3 builder/build.py <brief.md> [<more brief files>...] <tool_api.json> [--slot NAME] [--spec SPEC.json] [--no-chat]

1. Claude reads the brief(s) and the tool API into a spec (two independent readings, adjudication, validation).
2. The spec is checked locally: the in-agent engine is run against synthetic customers built from the spec.
3. The spec is compiled into a Freya workflow (a fixed, deterministic state machine + per-stage extraction).
4. The workflow is validated (dry run), saved and published, smoke-tested over chat, and exported.
Everything is written to traces/<slot>.log.
"""
import argparse
import copy
import json
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
KIT = ROOT / "kit" / "build-the-builder"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(KIT))
sys.path.insert(0, str(KIT / "tools"))

from builder.trace import Trace  # noqa: E402
from builder import compile as comp  # noqa: E402
from builder import selftest  # noqa: E402


REPAIRS = 3              # repair rounds for the whole pipeline
REPAIR_SECONDS = 15 * 60 # no repair round starts after this (the build limit is 30 minutes)


class Budget:
    def __init__(self, total, seconds):
        self.total, self.used, self.t0, self.seconds = total, 0, time.time(), seconds

    def take(self, trace, purpose):
        if self.used >= self.total or time.time() - self.t0 > self.seconds:
            trace.note(f"repair budget exhausted ({self.used}/{self.total} rounds, {int(time.time() - self.t0)} s): no {purpose}")
            return False
        self.used += 1
        trace.note(f"repair round {self.used}/{self.total}: {purpose}")
        return True


def finalize(spec, openapi):
    """Lossless normalisation + what the tool API file decides (response fields, success flags, record shape)."""
    from builder import spec_model
    spec_model.normalise(spec)
    for k in ("system_prompt", "test_variables"):         # model output must never become the live agent's prompt
        spec.pop(k, None)
    return comp.apply_defaults(spec, openapi)


DOCS_TEXT = [""]                              # the materials, for the quote and code checks


PROTECTED = {"currency_word", "calendar", "callback", "confirm", "identity", "products", "bands", "ladder", "events",
             "tool_bodies", "lines", "max_not_talk", "calendar.workdays", "identity.questions", "products.names",
             "callback.days", "callback.start", "callback.end"}


def degrade(spec, openapi, rounds=12):
    """Last resort after the repair budget: remove the optional values the structural check rejects (a value the
    format cannot hold), one at a time, and list each under unsupported_rules so the build is INCOMPLETE, never
    silently 'fixed'. Required parts (bands, events, lines, identity questions...) are never removed: if those are
    still malformed the build stops as before."""
    from builder import spec_model
    spec, dropped = copy.deepcopy(spec), []
    for _ in range(rounds):
        errs = spec_model.check(finalize(copy.deepcopy(spec), openapi))
        if not errs:
            break
        raw_keys = [k for k in errs[0].split(":", 1)[0].strip().split(".") if k]
        keys, node = [], spec                  # Pydantic adds union-member tags (".str", ".dict[str,str]"): stop at the
        for k in raw_keys:                     # deepest key that really exists in the spec
            if isinstance(node, dict) and k in node:
                node = node[k]
            elif isinstance(node, list) and k.isdigit() and int(k) < len(node):
                node = node[int(k)]
            else:
                break
            keys.append(k)
        path = ".".join(keys)
        if not keys or path in PROTECTED or len(keys) == 1 and keys[0] in PROTECTED:
            break
        parent = spec
        for k in keys[:-1]:
            parent = parent[int(k)] if isinstance(parent, list) else parent[k]
        last = keys[-1]
        if not isinstance(parent, dict):
            break
        if isinstance(parent.get(last), (dict, list)) and path.count(".") < 1:
            break
        val = parent.pop(last)
        msg = f"{path} = {json.dumps(val, ensure_ascii=False)[:160]} could not be expressed ({errs[0].split(':', 1)[-1].strip()[:120]}); dropped"
        dropped.append(msg)
        spec.setdefault("unsupported_rules", []).append(msg)
    return spec, dropped


def local_checks(spec, openapi):
    from builder import extract, policy, spec_model
    results = selftest.run_all(spec, openapi)
    api = extract.validate(spec, openapi, DOCS_TEXT[0])
    if DOCS_TEXT[0]:
        api += policy.check(spec, DOCS_TEXT[0])[0]
    return dict(structural=spec_model.check(spec), api=api, results=results,
                failed=[n for n, ok, _ in results if not ok])


def report_checks(trace, chk, label):
    for e in chk["structural"]:
        trace.note(f"{label} structural problem: {e}")
    for name, ok, detail in chk["results"]:
        trace.test(f"{label} {name}", ok, detail)
    trace.note(f"{label} checks: structural {len(chk['structural'])}, tool API {len(chk['api'])}, "
               f"self-test {sum(r[1] for r in chk['results'])}/{len(chk['results'])}")


def repair_loop(spec, chk, openapi, docs, trace, budget):
    """Repairs after the local checks, bounded by the shared budget. A candidate is accepted only if it passes every
    local check again (structure, tool API, self-test) and is better without being worse anywhere."""
    from builder import extract
    while (chk["structural"] or chk["failed"]) and budget.take(trace, "repair after the local checks"):
        problems = ["Structural problems: " + "; ".join(chk["structural"])] if chk["structural"] else []
        problems += [f"- {n}: {d[:1500]}" for n, ok, d in chk["results"] if not ok]
        try:
            cand = finalize(extract.carry_audit(spec, extract.repair_behaviour(copy.deepcopy(spec), "\n".join(problems), docs, openapi, trace)), openapi)
        except Exception as e:
            trace.note(f"repair failed ({type(e).__name__}: {e}); keeping the current spec")
            break
        c2 = local_checks(cand, openapi)
        report_checks(trace, c2, "candidate")
        touched = extract.diff(spec, cand)
        id_failed = any("identity" in n for n in chk["failed"])
        score = lambda c: (len(c["structural"]), len(c["api"]), len(c["failed"]))
        not_worse = all(x <= y for x, y in zip(score(c2), score(chk)))
        new_failed = set(c2["failed"]) - set(chk["failed"])     # a scenario that passed before must still pass
        lost = extract.coverage(spec) - extract.coverage(cand)  # no stated value may be dropped
        more_unsup = len(cand.get("unsupported_rules") or []) > len(spec.get("unsupported_rules") or [])
        if new_failed or lost:
            trace.note("repair rejected: " + (f"new failures {sorted(new_failed)}" if new_failed else "") +
                       (f" dropped stated values {sorted(lost)[:6]}" if lost else ""))
            not_worse = False
        if "identity.questions" in touched and not id_failed and not chk["structural"]:
            trace.note("repair changed the identity questions although no identity scenario failed; rejected")
        elif not_worse and score(c2) < score(chk) and not more_unsup:
            spec, chk = cand, c2
            trace.note("repaired spec accepted")
        else:
            new_unsup = [r for r in cand.get("unsupported_rules") or [] if r not in (spec.get("unsupported_rules") or [])]
            if new_unsup:                     # the failure is a rule the format cannot carry: report it, change nothing else
                spec["unsupported_rules"] = list(spec.get("unsupported_rules") or []) + new_unsup
                trace.note(f"repair named {len(new_unsup)} rule(s) the spec cannot carry; reported, the spec is unchanged")
            trace.note("repaired spec not better; rejected. No further repair rounds: a failure a repair does not improve "
                       "is not a reading mistake (an engine limit or the synthetic test)")
            break
    return spec, chk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--slot")
    ap.add_argument("--spec", help="reuse a spec file instead of reading the brief (development only)")
    ap.add_argument("--no-chat", action="store_true")
    ap.add_argument("--no-deploy", action="store_true")
    a = ap.parse_args()
    if not a.no_deploy and not os.environ.get("FREYA_API_KEY"):
        sys.exit("FREYA_API_KEY is not set: nothing would be deployed (source env.sh first, or use --no-deploy)")
    tool_api = [f for f in a.files if f.endswith(".json")]
    briefs = [f for f in a.files if not f.endswith(".json")]
    if len(tool_api) != 1 or not briefs:
        sys.exit("usage: build.py <brief files...> <tool_api.json>")
    slot = a.slot or "+".join(pathlib.Path(b).stem for b in briefs)
    trace = Trace(str(ROOT / "traces" / f"{slot}.trace.log"))
    trace.note(f"briefs={briefs} tool_api={tool_api[0]} slot={slot}")
    openapi = json.load(open(tool_api[0]))
    docs = [(pathlib.Path(b).name, pathlib.Path(b).read_text(errors="ignore")) for b in briefs]
    DOCS_TEXT[0] = "\n".join(text for _, text in docs) + "\n" + json.dumps(openapi, ensure_ascii=False)

    # One budget for the whole pipeline: every repair round anywhere (validation repairs during extraction,
    # repairs after the local checks) takes one unit, and no repair starts after REPAIR_SECONDS.
    budget = Budget(REPAIRS, REPAIR_SECONDS)
    trace.step("1. spec extraction")
    if a.spec:
        spec = json.load(open(a.spec))
        trace.note(f"spec loaded from {a.spec} (no model call)")
    else:
        from builder import extract
        try:
            spec = extract.extract(docs, openapi, trace, budget)
        except Exception as e:                  # one more full attempt before giving up
            trace.note(f"extraction failed ({type(e).__name__}: {e}); trying once more")
            spec = extract.extract(docs, openapi, trace, budget)
    from builder import spec_model
    spec = finalize(spec, openapi)
    out_dir = ROOT / "submission"
    out_dir.mkdir(exist_ok=True)
    for asm in spec.get("assumptions", []):
        trace.note("assumption: " + str(asm))

    trace.step("2. local checks: structure, tool API, engine self-test on synthetic customers")
    chk = local_checks(spec, openapi)
    report_checks(trace, chk, "local")
    if not a.spec:
        spec, chk = repair_loop(spec, chk, openapi, docs, trace, budget)
    from builder import policy
    for a_ in spec_model.assumed(spec):          # a default where the brief is silent: visible, never hidden
        trace.note("assumption (engine default, the brief is silent): " + a_)
    for a_ in policy.assumptions(spec):
        trace.note("assumption (recorded as unspecified by the materials): " + a_)
    for u_ in policy.uncertain(policy.check(copy.deepcopy(spec), DOCS_TEXT[0])[1]):
        trace.note("uncertain (no evidence recorded for a critical policy): " + u_)
    for u in spec_model.unsupported(spec):    # valid policy the engine cannot carry out as written: say so, never change it
        trace.note("UNSUPPORTED by the engine (policy kept as the brief states it): " + u)
    if chk["structural"]:                     # never zero: drop what cannot be expressed, say so, deploy the rest
        spec, dropped = degrade(spec, openapi)
        if dropped:
            trace.note("DEGRADED: values the format cannot hold were dropped so an agent can still be deployed "
                       "(each is listed as not carried):" + "".join("\n  - " + d for d in dropped))
            chk = local_checks(spec, openapi)
            report_checks(trace, chk, "degraded")
    (out_dir / f"{slot}.spec.json").write_text(json.dumps(spec, indent=1, ensure_ascii=False))
    if chk["structural"]:                     # the engine only ever gets a structurally valid spec
        trace.note("STOP: the spec is still malformed; not deploying:" + "".join("\n  - " + e for e in chk["structural"]))
        trace.end()
        sys.exit("spec still malformed after the repair budget (see the trace); nothing deployed")
    trace.note(f"repair budget used: {budget.used}/{budget.total}")

    trace.step("3. compile workflow")
    try:
        wf = comp.compile_workflow(spec, openapi)
    except Exception as e:                    # e.g. the engine code is over the code-node budget
        trace.note(f"STOP: the workflow could not be compiled ({type(e).__name__}: {e}); nothing deployed")
        trace.end()
        sys.exit(f"workflow compile failed: {e}")
    n_tools = sum(len(n.get("pre_actions", [])) for n in wf["nodes"].values())
    trace.note(f"workflow: {len(wf['nodes'])} nodes, {n_tools} engine-run calls, {len(json.dumps(wf))} bytes")
    (out_dir / f"{slot}.compiled.json").write_text(json.dumps(wf, indent=1))

    if a.no_deploy:
        finish(trace, spec, chk)
        return
    os.environ.setdefault("FREYA_RETRIES", "6")   # deploy calls: 6 tries 10 s apart before giving up (platform 5xx)
    import freya
    trace.step("4. validate, save, publish")
    try:
        freya.validate_workflow(slot, wf)
        trace.test("platform dry-run validation", True)
        ids = freya.save_workflow(slot, wf, state_file=str(ROOT / ".freya-agents.json"))
    except Exception as e:                    # the platform, not the spec: keep the extraction, say how to resume
        trace.note(f"DEPLOY FAILED (platform): {str(e)[:300]}. The spec is saved; resume without a new extraction: "
                   f"python3 builder/build.py {' '.join(a.files)} --slot {slot} --spec submission/{slot}.spec.json")
        trace.end()
        sys.exit(4)
    trace.note(f"FREYA workflow_id={ids['workflow_id']} agent_id={ids['agent_id']} version={ids.get('version', 1)}")

    if not a.no_chat:
        trace.step("5. chat smoke test on Freya")
        for name, ok, detail in selftest.chat_smoke(freya, ids["workflow_id"], spec):
            trace.test("chat " + name, ok, detail)

    trace.step("6. export")
    path = out_dir / f"{slot}.workflow.json"
    try:
        freya.export_workflow(ids["workflow_id"], str(path))
    except Exception as e:
        trace.note(f"EXPORT FAILED (platform): {str(e)[:300]}. The agent is published (workflow_id={ids['workflow_id']}); "
                   f"export it again with freya.export_workflow before submitting")
        trace.end()
        sys.exit(4)
    trace.note(f"exported {path.relative_to(ROOT)}")
    print(json.dumps({"workflow_id": ids["workflow_id"], "agent_id": ids["agent_id"], "export": str(path.relative_to(ROOT))}))
    finish(trace, spec, chk)


def finish(trace, spec, chk):
    """The run's verdict. INCOMPLETE when a rule of the materials is not carried or a local scenario still fails:
    the agent exists and is exported, but the run is not reported as a success (exit status 3)."""
    from builder import spec_model
    gaps = spec_model.critical(spec) + [f"local scenario fails: {n}" for n in chk.get("failed", [])] + \
        [f"spec problem left after the repairs: {e}" for e in chk.get("api", [])]
    for d in (spec.get("oracle_report") or {}).get("disagreements") or []:
        trace.note("UNCERTAIN (the independent reading disagrees; the materials were not decided either way): " + d)
    if gaps:
        trace.note("RESULT: INCOMPLETE -- the agent does not meet these:" + "".join("\n  - " + g for g in gaps))
        trace.end()
        sys.exit(3)
    trace.note("RESULT: COMPLETE -- every rule carried, every local scenario passes")
    trace.end()


if __name__ == "__main__":
    main()
