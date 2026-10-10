"""promptfoo assertion: scores the extracted spec against the package's frozen key (eval/score.py)."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))
import score  # noqa: E402


def get_assert(output, context):
    rec = json.loads(output)
    spec = json.load(open(rec["spec_path"]))
    res = score.score(spec, ROOT / "eval" / "packages" / rec["pkg"])
    rec_path = pathlib.Path(rec["spec_path"]).with_suffix(".score.json")
    json.dump(dict(res, **{k: rec[k] for k in ("mode", "pkg", "seconds", "cost", "calls", "repairs", "error")}),
              open(rec_path, "w"), indent=1, default=str)
    missed = res["missed_rules"]
    return {"pass": res["ok"] == res["total"], "score": res["accuracy"],
            "reason": f"{res['ok']}/{res['total']} checks; missed rules {missed}; {rec['seconds']}s ${rec['cost']}; "
                      f"repairs {rec['repairs']}" + (f"; error {rec['error']}" if rec["error"] else ""),
            "namedScores": {"accuracy": res["accuracy"], "missed_rules": len(missed),
                            "seconds": rec["seconds"], "cost_usd": rec["cost"]}}
