"""Platform probe of the stale-answer path (no new customer message while an old 'yes' is still in the variable).
A real engine state at the read-back is built locally (PUB-01, the same products the practice bank returns), then
injected as call variables on the first chat message together with confirm_kind='yes'. The first chat message is a
customer turn the engine has already counted (turns_seen = 1), so the step must not take the old yes as an answer.
Then a fresh explicit 'Yes, I confirm.' must write exactly once, and a repeat must not write again.
    python3 eval/ambiguity/stale_probe.py <workflow_id> <out.json>"""
import copy, json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "kit/build-the-builder")); sys.path.insert(0, str(ROOT / "kit/build-the-builder/tools"))
import freya
from score import http
from builder import selftest
from builder import compile as comp
wf_id, out = sys.argv[1], sys.argv[2]
OA = json.load(open(ROOT / "kit/build-the-builder/tools/openapi.json"))
SA = json.load(open(ROOT / "eval/clean-runs/cand8-a/cand8-a.spec.json"))
case = [c for c in json.load(open(ROOT / "kit/build-the-builder/public-test-set.json")) if c["id"] == "PUB-01"][0]
spec = comp.apply_defaults(copy.deepcopy(SA), OA); wf = comp.compile_workflow(spec, OA)
prods = [dict(p, product_id=f"p{i + 1}") for i, p in enumerate(case["products"])]
bank = selftest.GenericBank(copy.deepcopy(spec), case["identity"], prods)
sess = http("/v1/practice/sessions", {"case": "PUB-01"})["variables"]
V = dict(sess)
T = lambda k, t, d="": dict(k=k, t=t, d=d, a="", f="none", side="none", cut="no")
def feed(stage, u):
    V.update({stage + "_kind": u.get("k", "none"), stage + "_text": u.get("t", ""), stage + "_date": u.get("d", ""),
              stage + "_amount": "", stage + "_side": "none", stage + "_for": "none", stage + "_cut": "no"})
    if stage == "id": V["id_norm"] = u.get("norm", "")
selftest.COUNTERS[0] = False
selftest.walk(wf, spec, V, lambda tool, body, slots: bank.call(tool, slots),
              [T("confirmed", "yes"), dict(k="answer", t="14 March 1988", norm="1988-03-14"), dict(k="answer", t="4471", norm="4471"),
               T("proposes", "I can pay the full amount on Friday.", "Friday")], feed, 400)
st = json.loads(V["_state"]); st["turns_seen"] = 1; st["await"] = "talk"
inject = dict(sess, _state=json.dumps(st), say=V["say"], confirm_kind="yes", confirm_text="Yes, I confirm.", confirm_cut="no")
res, cid = [], None
for i, m in enumerate(["Hello?", "Yes, I confirm.", "Yes, I confirm."]):
    body = {"workflowId": wf_id, "message": m, "customerVariables": inject if i == 0 else sess}
    if cid: body["callId"] = cid
    r = freya.api("POST", "/api/v2/chat/message", body); cid = r.get("callId", cid)
    led = http("/v1/practice/ledger/" + sess["customer_id"])
    res.append(dict(user=m, agent=r.get("response", ""), writes=[c["tool"] for c in led.get("calls", []) if c["tool"] == "create_promise"]))
    print(f"U: {m!r}\nA: {r.get('response','')[:150]!r}\n   create_promise calls so far: {len(res[-1]['writes'])}")
try: freya.api("POST", "/api/v2/chat/end", {"callId": cid})
except Exception: pass
led = http("/v1/practice/ledger/" + sess["customer_id"])
print("ledger:", [(c["tool"], c.get("args"), c.get("result")) for c in led.get("calls", [])])
pathlib.Path(out).write_text(json.dumps(dict(call_id=cid, turns=res, ledger=led), indent=1))
