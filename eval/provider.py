"""promptfoo provider: runs the builder's spec extraction on one frozen package in mode A or B.

Mode A (default in the builder): two independent readings, field diff, adjudication of disagreements.
Mode B: one strong reading, then a targeted audit of the high-risk fields against the source documents.
Both then go through the same validation loop under the same shared repair budget (build.Budget).
The prompt is the package name; the output is a small JSON record (spec path, seconds, cost, calls, repairs).
"""
import json
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PKGS = ROOT / "eval" / "packages"
RUNS = ROOT / "eval" / "runs"


def call_api(prompt, options, context):
    mode = (options.get("config") or {}).get("mode", "A")
    pkg = prompt.strip()
    os.environ["BUILDER_EXTRACT_MODE"] = mode[0]
    guidance = (options.get("config") or {}).get("guidance")
    if guidance:
        os.environ["BUILDER_EXTRACT_GUIDANCE"] = str(ROOT / "eval" / guidance)
        mode = mode + "+gepa"
    if mode.startswith("B_high"):
        os.environ["BUILDER_B_EFFORT"] = "high"
    from builder import extract
    from builder.build import REPAIR_SECONDS, REPAIRS, Budget
    from builder.trace import Trace
    stamp = time.strftime("%H%M%S") + f"-{os.getpid()}"
    RUNS.mkdir(exist_ok=True)
    name = f"{pkg}-{mode}-{stamp}"
    trace = Trace(str(RUNS / f"{name}.trace.log"))
    docs = [("brief.md", (PKGS / pkg / "brief.md").read_text())]
    openapi = json.load(open(PKGS / pkg / "openapi.json"))
    budget = Budget(REPAIRS, REPAIR_SECONDS)
    t0 = time.time()
    try:
        spec = extract.extract(docs, openapi, trace, budget)
        err = ""
    except Exception as e:
        spec, err = {}, f"{type(e).__name__}: {e}"
    sec = time.time() - t0
    trace.end()
    path = RUNS / f"{name}.spec.json"
    json.dump(spec, open(path, "w"), indent=1)
    rec = dict(spec_path=str(path), mode=mode, pkg=pkg, seconds=round(sec, 1), cost=round(trace.cost, 4),
               calls=trace.calls, repairs=budget.used, error=err)
    return {"output": json.dumps(rec), "cost": trace.cost}
