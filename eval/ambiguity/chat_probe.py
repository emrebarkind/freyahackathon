"""A few ambiguous turns through the platform's real extraction path (chat route, candidate 8 brief-A workflow),
against a real practice-bank session. Prints, per customer turn, the extracted variables and the agent's reply,
then the bank ledger. Not a simulation run.
    python3 eval/ambiguity/chat_probe.py <workflow_id> <out.json> [script,script]"""
import json, pathlib, sys, time
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit/build-the-builder")); sys.path.insert(0, str(ROOT / "kit/build-the-builder/tools"))
import freya
from score import http
wf, out = sys.argv[1], sys.argv[2]
SCRIPTS = {
 "confirm-ambiguity": ["Hello?", "Yes, this is Daniel Reyes.", "14 March 1988.", "4471.", "I can pay the full amount today.",
                       "uh...", "I was thinking...", "Yes, I confirm.", "No, that's all."],
 "correction-and-noise": ["Hello?", "Yes, this is Daniel Reyes.", "14 March 1988.", "4471.", "Yes... no, Friday does not work.",
                          "hmm...", "thought\nThe user is asking for the payment date", "Traffic was awful today. I can pay the full amount on the 20th.",
                          "Yes, I confirm.", "No, thank you."],
 "amount-digits-pieces": ["Hello?", "Yes, this is Daniel Reyes.", "14 March 1988.", "4471.", "I cannot pay today. I can pay 300...",
                          "50 on Friday.", "Three hundred dollars and fifty cents, on Friday.", "Yes, I confirm.", "No, thank you."],
 "repeat-question": ["Hello?", "Yes, this is Daniel Reyes.", "14 March 1988.", "4471.", "Which account is this about?",
                     "Which account is this about?", "Which account is this about?", "OK. I can pay the full amount today.", "Yes, I confirm.", "No, thank you."],
 "rejected-day": ["Hello?", "Yes, this is Daniel Reyes.", "14 March 1988.", "4471.", "Yes... no, Friday does not work.", "Yes.",
                  "I can pay the full amount on the 20th.", "Yes, I confirm.", "No, thank you."],
 "pub10-reentry": ["Hello?", "Yes, this is Grace Lin.", "23 February 1989.", "9904.", "I can't pay today. I will pay the full amount this Friday.",
                   "Yes, I confirm.", "No, that is all."],
 "fragmented-amount": ["Hello?", "Yes, this is Daniel Reyes.", "14 March 1988.", "4471.", "I cannot pay today. My salary...",
                       "I can pay three hundred and", "fifty dollars on Friday.", "aaa...", "Yes, I confirm.", "No."],
}
res = {}
ONLY = sys.argv[3].split(',') if len(sys.argv) > 3 else list(SCRIPTS)
for name, msgs in [(n, m) for n, m in SCRIPTS.items() if n in ONLY]:
    sess = http("/v1/practice/sessions", {"case": "PUB-10" if name.startswith("pub10") else "PUB-01"})["variables"]
    cid, turns = None, []
    for m in msgs:
        body = {"workflowId": wf, "message": m, "customerVariables": sess}
        if cid: body["callId"] = cid
        t0 = time.time()
        try:
            r = freya.api("POST", "/api/v2/chat/message", body)
        except Exception as e:
            turns.append(dict(user=m, error=str(e)[:200])); break
        cid = r.get("callId", cid)
        turns.append(dict(user=m, agent=r.get("response", ""), s=round(time.time() - t0, 1)))
    try: freya.api("POST", "/api/v2/chat/end", {"callId": cid})
    except Exception: pass
    ext = []
    try:
        call = freya.get_call(cid); call = call.get("call") or call
        for x in call.get("messages", []):
            if x.get("role") == "system" and '"variable_extracted"' in str(x.get("message")):
                e = json.loads(x["message"])
                if e.get("name", "").split("_")[0] in ("nego", "confirm") and e["name"].rsplit("_", 1)[-1] in ("kind", "cut", "date", "amount"):
                    ext.append((e["name"], e["value"], (e.get("input_text") or "")[:60]))
    except Exception as e:
        ext.append(("error", str(e)[:200], ""))
    led = http("/v1/practice/ledger/" + sess["customer_id"])
    res[name] = dict(call_id=cid, turns=turns, extracted=ext, ledger=[(c["tool"], c.get("args"), c.get("result")) for c in led.get("calls", [])])
    print("=====", name, cid)
    for t in turns: print(" U:", repr(t["user"])[:70], "\n A:", repr(t.get("agent") or t.get("error"))[:150])
    for e in ext: print("   X", e)
    for l in res[name]["ledger"]: print("   L", l[0], json.dumps({k: v for k, v in (l[1] or {}).items() if k != "answer"})[:90], json.dumps(l[2])[:60])
pathlib.Path(out).write_text(json.dumps(res, indent=1))
