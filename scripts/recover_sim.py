"""Rebuild the scored rows of a simulation whose client (run_cases.py) was lost, without running it again.
The judge's verdict comes from the platform; the bank record from the practice ledger, using the customer ids that
run_cases.py journaled at start (results/sim-journal.jsonl), or, failing that, the customer_id the agent sent in its
own tool calls. A run the platform retried is reported with its attempt number, and its ledger may hold the calls
of both attempts (the session is the same).
    python3 scripts/recover_sim.py <simulation_id> [--out path.json]"""
import argparse, json, pathlib, re, sys
KIT = pathlib.Path(__file__).resolve().parent.parent / "kit" / "build-the-builder"
sys.path.insert(0, str(KIT)); sys.path.insert(0, str(KIT / "tools"))
import freya
from score import http, score_ledger

ap = argparse.ArgumentParser(); ap.add_argument("sim_id"); ap.add_argument("--out"); a = ap.parse_args()
cases = {c["id"]: c for c in json.load(open(KIT / "public-test-set.json"))}
journal = {}
jp = KIT / "results" / "sim-journal.jsonl"
if jp.exists():
    for line in open(jp):
        e = json.loads(line)
        if e.get("sim_id") == a.sim_id and e.get("event") == "started":
            journal = e
sim = freya.api("GET", f"/api/v2/simulations/{a.sim_id}"); sim = sim.get("simulation") or sim
its = freya.api("GET", f"/api/v2/simulations/{a.sim_id}/iterations"); its = its.get("iterations") or its.get("items") or its
it = freya.get_iteration(a.sim_id, its[0]["id"])
print(f"simulation {a.sim_id} status {sim.get('status')} agent {sim.get('agentId')} retries allowed {sim.get('settings', {}).get('maxRetries')}")
rows = []
for r in it["runs"]:
    cid = (r.get("personaName") or "").split(" ")[0]
    c = cases.get(cid)
    if not c:
        continue
    cust = (journal.get("customer_ids") or {}).get(cid)
    if not cust and r.get("callId"):
        found = re.findall(r'customer_id[\\"]*[:=][\\" ]*(c_[A-Za-z0-9_\-]{6,})', json.dumps(freya.get_call(r["callId"])))
        cust = found[0] if found else None
    led = http("/v1/practice/ledger/" + cust) if cust else {"calls": []}
    res = score_ledger(c, led) if cust else {"failed": ["ledger not found (no customer id)"]}
    if r.get("outcome") != "pass":
        res["failed"].append("conversation: " + " ".join(str(r.get("reason") or "no verdict").split())[:400])
    row = dict(id=cid, family=c["family"], pass_=not res["failed"], failed=res["failed"], call_id=r.get("callId"),
               customer_id=cust, attempts=r.get("attempts"), tools=[x["tool"] for x in led.get("calls", [])])
    rows.append(row)
    print(("PASS" if row["pass_"] else "FAIL"), cid, f"attempt {row['attempts']}", "|",
          " > ".join(t.replace("verify_identity", "verify").replace("create_promise", "promise") for t in row["tools"]))
    for f in row["failed"]:
        print("       -", f[:260])
print(f"\n{sum(r['pass_'] for r in rows)} / {len(rows)} passed (recovered from the platform, not re-run)")
if a.out:
    pathlib.Path(a.out).write_text(json.dumps(dict(simulation_id=a.sim_id, recovered=True, rows=rows), indent=1))
