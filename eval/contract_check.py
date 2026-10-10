"""openapi-core experiment: are the request bodies the compiled workflow actually sends valid under the tool API?

1. Baseline: run the local self-test scenarios (selftest.run_all) on real specs, record every request body the
   compiled api nodes send, and validate each against the OpenAPI file with openapi-core.
2. Seeded faults: break a spec in ways a misreading could (renamed body field, dropped required field, codes not
   in an enum, wrong identity field) and compare who notices: the existing checks (extract.validate) or
   openapi-core on the bodies. A schema-valid body can still be wrong for the business (wrong customer, wrong
   success meaning); this measures contract conformance only.

    python3 eval/contract_check.py
"""
import copy
import json
import pathlib
import sys

from openapi_core import OpenAPI
from openapi_core.testing import MockRequest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from builder import compile as comp, extract, selftest, spec_model  # noqa: E402

KIT = ROOT / "kit" / "build-the-builder" / "tools" / "openapi.json"
PAIRS = [("A", "submission/brief-a.spec.json", KIT), ("B", "submission/brief-b.spec.json", KIT),
         ("C", "submission/variant-c.spec.json", "variants/brief-c.openapi.json"),
         ("D", "submission/variant-d.spec.json", "variants/brief-d.openapi.json"),
         ("E", "submission/variant-e.spec.json", "variants/brief-e.openapi.json"),
         ("F", "submission/rehearsal-f.spec.json", "rehearsal/brief-f.openapi.json")]


def bodies(spec, openapi):
    """Every (tool, body) the compiled workflow sends during the self-test scenarios."""
    sent, orig = [], selftest.walk

    def walk(wf, spec_, V, bank_call, *a, **k):
        def call(tool, body, slots):
            sent.append((tool, copy.deepcopy(body)))
            return bank_call(tool, body, slots)
        return orig(wf, spec_, V, call, *a, **k)
    selftest.walk = walk
    try:
        selftest.run_all(copy.deepcopy(spec), openapi)
    finally:
        selftest.walk = orig
    return sent


def contract_errors(openapi, sent):
    doc = copy.deepcopy(openapi)
    doc["servers"] = [{"url": "http://localhost"}]     # validate the bodies, not the host
    api = OpenAPI.from_dict(doc)
    host = "http://localhost"
    out = set()
    for tool, body in sent:
        req = MockRequest(host, "post", "/" + tool, data=json.dumps(body), content_type="application/json")
        try:
            api.validate_request(req)
        except Exception as e:
            causes = [str(x) for x in (getattr(e, "schema_errors", None) or [])] or \
                     [str(getattr(e, "__cause__", "") or e)]
            for c in causes:
                out.add(f"{tool}: {c.splitlines()[0][:160]}")
    return out


def body_schema(openapi, tool):
    return openapi["paths"]["/" + tool]["post"]["requestBody"]["content"]["application/json"]["schema"]


def faults(spec, openapi):
    """(name, mutated spec) pairs; each breaks the contract in one way."""
    out = []
    tb = spec["tool_bodies"]
    cp_field = next((f for f, v in tb.get("create_promise", {}).items() if v == "p_amount"), None)
    if cp_field:
        s = copy.deepcopy(spec)
        s["tool_bodies"]["create_promise"]["amount_value"] = s["tool_bodies"]["create_promise"].pop(cp_field)
        out.append(("renamed create_promise amount field", s))
    req = [f for f in body_schema(openapi, "add_note").get("required", []) if f in tb.get("add_note", {})]
    if req:
        s = copy.deepcopy(spec)
        s["tool_bodies"]["add_note"].pop(req[-1])
        out.append((f"dropped required add_note.{req[-1]}", s))
    s = copy.deepcopy(spec)
    s["events"]["refused"]["outcome"] = "not_a_code"
    out.append(("close outcome not in enum", s))
    s = copy.deepcopy(spec)
    s["events"]["refused"]["reason"] = "not_a_reason"
    out.append(("close reason not in enum", s))
    s = copy.deepcopy(spec)
    for e in s["events"].values():
        if e.get("note"):
            e["note"] = "not_a_note"
    out.append(("note reason not in enum", s))
    s = copy.deepcopy(spec)
    for e in s["events"].values():
        if e.get("queue"):
            e["queue"] = "not_a_queue"
    out.append(("transfer queue not in enum", s))
    s = copy.deepcopy(spec)
    s["identity"]["questions"][0]["field"] = "not_a_field"
    out.append(("identity field not in enum", s))
    s = copy.deepcopy(spec)
    tbc = s["tool_bodies"]["close_call"]
    k = next((f for f, v in tbc.items() if v == "c_outcome"), None)
    if k:
        tbc["outcome_code"] = tbc.pop(k)
        out.append(("renamed close_call outcome field", s))
    return out


def prepared(spec, openapi):
    s = copy.deepcopy(spec)
    spec_model.normalise(s)
    return comp.apply_defaults(s, openapi)


def main():
    report = dict(baseline={}, faults=[])
    for name, sp, op in PAIRS:
        openapi = json.load(open(ROOT / op))
        raw = json.load(open(ROOT / sp))
        spec = prepared(raw, openapi)
        sent = bodies(spec, openapi)
        base_oc = contract_errors(openapi, sent)
        base_v = set(extract.validate(copy.deepcopy(raw), openapi))
        report["baseline"][name] = dict(requests=len(sent), tools=sorted({t for t, _ in sent}),
                                        openapi_core=sorted(base_oc), validate=sorted(base_v))
        print(f"{name}: {len(sent)} requests, openapi-core violations {len(base_oc)}, validate problems {len(base_v)}")
        for e in sorted(base_oc):
            print("   oc:", e)
        for fname, bad in faults(raw, openapi):
            v_new = set(extract.validate(copy.deepcopy(bad), openapi)) - base_v
            try:
                oc_new = contract_errors(openapi, bodies(prepared(bad, openapi), openapi)) - base_oc
                oc_err = ""
            except Exception as e:
                oc_new, oc_err = set(), f"{type(e).__name__}: {str(e)[:120]}"
            row = dict(pair=name, fault=fname, validate=bool(v_new), openapi_core=bool(oc_new),
                       validate_msg=sorted(v_new)[:2], oc_msg=sorted(oc_new)[:2], oc_error=oc_err)
            report["faults"].append(row)
            print(f"   fault {fname:38} validate={'Y' if v_new else '-'} openapi-core={'Y' if oc_new else '-'}" + (f"  ({oc_err})" if oc_err else ""))
    rows = report["faults"]
    print(f"\nseeded faults: {len(rows)}; caught by validate {sum(r['validate'] for r in rows)}, by openapi-core "
          f"{sum(r['openapi_core'] for r in rows)}, only by openapi-core {sum(r['openapi_core'] and not r['validate'] for r in rows)}, "
          f"only by validate {sum(r['validate'] and not r['openapi_core'] for r in rows)}, by neither {sum(not r['validate'] and not r['openapi_core'] for r in rows)}")
    out = ROOT / "eval" / "out"
    out.mkdir(exist_ok=True)
    json.dump(report, open(out / "contract_check.json", "w"), indent=1)


if __name__ == "__main__":
    main()
