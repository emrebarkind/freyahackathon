"""Build the Builder -- one command, brief(s) in, tested Freya phone agent out.

    python3 builder/build.py <brief.md> [<more brief files>...] <tool_api.json> [--slot NAME] [--spec SPEC.json] [--no-chat]

1. Claude reads the brief(s) and the tool API into a spec (two independent readings, adjudication, validation).
2. The spec is checked locally: the in-agent engine is run against synthetic customers built from the spec.
3. The spec is compiled into a Freya workflow (a fixed, deterministic state machine + per-stage extraction).
4. The workflow is validated (dry run), saved and published, smoke-tested over chat, and exported.
Everything is written to traces/<slot>.log.
"""
import argparse
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--slot")
    ap.add_argument("--spec", help="reuse a spec file instead of reading the brief (development only)")
    ap.add_argument("--no-chat", action="store_true")
    ap.add_argument("--no-deploy", action="store_true")
    a = ap.parse_args()
    tool_api = [f for f in a.files if f.endswith(".json")]
    briefs = [f for f in a.files if not f.endswith(".json")]
    if len(tool_api) != 1 or not briefs:
        sys.exit("usage: build.py <brief files...> <tool_api.json>")
    slot = a.slot or "+".join(pathlib.Path(b).stem for b in briefs)
    trace = Trace(str(ROOT / "traces" / f"{slot}.trace.log"))
    trace.note(f"briefs={briefs} tool_api={tool_api[0]} slot={slot}")
    openapi = json.load(open(tool_api[0]))
    docs = [(pathlib.Path(b).name, pathlib.Path(b).read_text(errors="ignore")) for b in briefs]

    trace.step("1. spec extraction")
    if a.spec:
        spec = json.load(open(a.spec))
        trace.note(f"spec loaded from {a.spec} (no model call)")
    else:
        from builder import extract
        try:
            spec = extract.extract(docs, openapi, trace)
        except Exception as e:                  # one more full attempt before giving up
            trace.note(f"extraction failed ({type(e).__name__}: {e}); trying once more")
            spec = extract.extract(docs, openapi, trace)
    comp.apply_defaults(spec, openapi)       # response field names / success flags come from the tool API file
    from builder import spec_model
    for u in spec_model.unsupported(spec):    # valid policy the engine cannot carry out as written: say so, do not change it
        trace.note("UNSUPPORTED by the engine (policy kept as the brief states it): " + u)
    errs = spec_model.check(spec)             # the engine only gets a structurally valid spec
    if errs and not a.spec:
        trace.note("structural problems before deploy:" + "".join("\n  - " + e for e in errs))
        try:
            from builder import extract
            fixed = comp.apply_defaults(extract.repair_behaviour(spec, "Structural problems: " + "; ".join(errs), docs, openapi, trace), openapi)
            if not spec_model.check(fixed) and len(extract.validate(fixed, openapi)) <= len(extract.validate(spec, openapi)):
                spec, errs = fixed, []
        except Exception as e:
            trace.note(f"structural repair failed ({type(e).__name__}: {e})")
    if errs:
        trace.note("STOP: the spec is still malformed; not deploying:" + "".join("\n  - " + e for e in errs))
        trace.end()
        sys.exit("spec still malformed after repair (see the trace); nothing deployed")
    out_dir = ROOT / "submission"
    out_dir.mkdir(exist_ok=True)
    (out_dir / f"{slot}.spec.json").write_text(json.dumps(spec, indent=1, ensure_ascii=False))
    for asm in spec.get("assumptions", []):
        trace.note("assumption: " + str(asm))

    trace.step("2. local self-test of the engine on synthetic customers")
    results = selftest.run_all(spec, openapi)
    for name, ok, detail in results:
        trace.test("local " + name, ok, detail)
    trace.note(f"local self-test: {sum(r[1] for r in results)}/{len(results)} passed")
    failed = [r for r in results if not r[1]]
    if failed and not a.spec:
        trace.step("2b. one repair round driven by the failed self-test scenarios")
        try:
            from builder import extract
            fixed = comp.apply_defaults(extract.repair_behaviour(
                spec, "\n".join(f"- {n}: {d[:1500]}" for n, _, d in failed), docs, openapi, trace), openapi)
            r2 = selftest.run_all(fixed, openapi)
            n_err, n_err2 = len(extract.validate(spec, openapi)), len(extract.validate(fixed, openapi))
            trace.note(f"repaired spec: self-test {sum(r[1] for r in r2)}/{len(r2)}, validation problems {n_err2} (before {n_err})")
            touched = extract.diff(spec, fixed)
            id_failed = any("identity" in n for n, _, _ in failed)
            if "identity.questions" in touched and not id_failed:
                trace.note("repair changed the identity questions although no identity scenario failed; rejected")
            elif n_err2 <= n_err and sum(not r[1] for r in r2) < len(failed):
                spec, results = fixed, r2
                (out_dir / f"{slot}.spec.json").write_text(json.dumps(spec, indent=1, ensure_ascii=False))
                for name, ok, detail in results:
                    trace.test("local (after repair) " + name, ok, detail)
            else:
                trace.note("repair not better; keeping the first spec")
        except Exception as e:
            trace.note(f"repair round failed ({type(e).__name__}: {e}); keeping the first spec")

    trace.step("3. compile workflow")
    wf = comp.compile_workflow(spec, openapi)
    n_tools = sum(len(n.get("pre_actions", [])) for n in wf["nodes"].values())
    trace.note(f"workflow: {len(wf['nodes'])} nodes, {n_tools} engine-run calls, {len(json.dumps(wf))} bytes")
    (out_dir / f"{slot}.compiled.json").write_text(json.dumps(wf, indent=1))

    if a.no_deploy:
        trace.end()
        return
    import freya
    trace.step("4. validate, save, publish")
    freya.validate_workflow(slot, wf)
    trace.test("platform dry-run validation", True)
    ids = freya.save_workflow(slot, wf, state_file=str(ROOT / ".freya-agents.json"))
    trace.note(f"FREYA workflow_id={ids['workflow_id']} agent_id={ids['agent_id']} version={ids.get('version', 1)}")

    if not a.no_chat:
        trace.step("5. chat smoke test on Freya")
        for name, ok, detail in selftest.chat_smoke(freya, ids["workflow_id"], spec):
            trace.test("chat " + name, ok, detail)

    trace.step("6. export")
    path = out_dir / f"{slot}.workflow.json"
    freya.export_workflow(ids["workflow_id"], str(path))
    trace.note(f"exported {path.relative_to(ROOT)}")
    print(json.dumps({"workflow_id": ids["workflow_id"], "agent_id": ids["agent_id"], "export": str(path.relative_to(ROOT))}))
    trace.end()


if __name__ == "__main__":
    main()
