"""Live check of the semantic policy audit (extract.AUDIT): one real audit call per case, the verdict on one
critical path compared with the expected verdict(s) fixed below before running. Writes eval/audit_cases/result.json.
    python3 eval/audit_cases/run.py
"""
import copy
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from builder import claude, extract, policy  # noqa: E402


def load(p):
    return json.load(open(ROOT / p))


def case_default_contradicts():
    spec = load("eval/branch-results/c4/test-sg3-p1-a.spec.json")
    spec["rules"].pop("skipped_repeat_counts", None)              # the default (a skipped step counts) applies
    spec.pop("sources", None)
    spec.pop("policy", None)
    return "eval/packages/p1", spec, "rules.skipped_repeat_counts", {"contradicted"}, False


def case_quote_does_not_support():
    spec = load("eval/branch-results/c4/test-sg3-p1-a.spec.json")
    spec.pop("sources", None)
    spec["rules"]["promise_retries"] = 3
    spec["policy"] = {"rules.promise_retries": {"kind": "explicit", "quotes": [
        "Never propose the same amount on the same date twice."]}}
    return "eval/packages/p1", spec, "rules.promise_retries", {"quote_does_not_support", "contradicted"}, None


def case_derived():
    spec = load("eval/branch-results/c4/test-sg4-r2.spec.json")
    spec.pop("sources", None)
    spec["policy"] = {"rules.opening_blocks_repeat": {"kind": "derived", "quotes": [
        "This opening question is not a ladder step and does not count toward the limit.",
        "Before proposing a step, compare it with every proposal already made in this call, the opening question included."],
        "derivation": "the opening ask is not a ladder step, but rule 17 compares a step with it: a step equal to the "
                      "opening ask is skipped"}}
    return "eval/robust/r2", spec, "rules.opening_blocks_repeat", {"supported"}, True


def case_memo_override():
    spec = load("submission/rehearsal-aprime2.spec.json")
    spec.pop("sources", None)
    spec["rules"].pop("hardship_transfer", None)                 # default: offer the transfer first (rule 32)
    spec["policy"] = {"rules.hardship_transfer": {"kind": "explicit", "quotes": [
        "Offer to connect them with the customer support team."]}}
    return "eval/platform/aprime", spec, "rules.hardship_transfer", {"contradicted"}, "direct"


CASES = [case_default_contradicts, case_quote_does_not_support, case_derived, case_memo_override]


class Trace:
    def __init__(self):
        self.calls = []

    def note(self, s):
        pass

    def model_call(self, *a, **k):
        self.calls.append((a, k))


def main():
    jobs, meta = [], []
    for f in CASES:
        pkg, spec, path, expect, want_value = f()
        docs = [("brief.md", (ROOT / pkg / "brief.md").read_text())]
        api = load(pkg + "/openapi.json")
        jobs.append((extract.prompt_for(docs, api) + "\n\n" + extract.audit_prompt(spec), extract.SYSTEM, f"audit case {f.__name__}"))
        meta.append((f.__name__, spec, path, expect, want_value))
    t0 = time.time()
    tr = claude_trace()
    outs = claude.ask_many(jobs, tr)
    rows = []
    for (name, spec, path, expect, want), out in zip(meta, outs):
        try:
            ans = claude.json_block(out)
        except Exception as e:
            rows.append(dict(case=name, path=path, verdict=None, ok=False, error=str(e)))
            continue
        fixed = extract.apply_audit(copy.deepcopy(spec), ans, tr)
        verdict = (ans.get("verdicts") or {}).get(path)
        val, _ = policy.effective(fixed, path)
        ok = verdict in expect and (want is None or val == want)
        line = next((ln for ln in out.split("```")[0].splitlines() if path.split(".")[-1] in ln), "")
        rows.append(dict(case=name, path=path, expected=sorted(expect), verdict=verdict, value_after=val,
                         expected_value=want, unresolved=fixed["policy_audit"]["unresolved"], ok=ok, line=line[:400]))
    res = dict(seconds=round(time.time() - t0), cost_usd=round(sum(c.get("cost", 0) for c in tr.costs), 3), rows=rows,
               passed=sum(r["ok"] for r in rows), total=len(rows))
    (ROOT / "eval/audit_cases/result.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))


def claude_trace():
    class TT:
        costs = []

        def note(self, s):
            pass

        def model_call(self, model, purpose, seconds, cost):
            self.costs.append({"cost": cost or 0})

        def step(self, s):
            pass
    return TT()


if __name__ == "__main__":
    main()
