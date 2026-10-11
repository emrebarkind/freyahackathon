"""Rebuild the scored rows of a simulation whose client (run_cases.py) was lost, without running it again.
The judge's verdict comes from the platform; the bank record from the practice ledger, using the customer ids that
run_cases.py journaled at start (results/sim-journal.jsonl), or, failing that, the customer_id the agent sent in its
own tool calls. A run the platform retried is reported with its attempt number, and its ledger may hold the calls
of both attempts (the session is the same).
Every recovery is a new snapshot, nothing is overwritten: the platform's own records as received (simulation,
iteration, each call, each ledger) go gzipped to eval/sim-records/<simulation_id>/<UTC time>/, next to the scored rows.
--out names a summary file; the UTC time is added to its name, and an existing file is never replaced.
    python3 scripts/recover_sim.py <simulation_id> [--out path.json]"""
import argparse, datetime, gzip, json, pathlib, re, sys
KIT = pathlib.Path(__file__).resolve().parent.parent / "kit" / "build-the-builder"
sys.path.insert(0, str(KIT)); sys.path.insert(0, str(KIT / "tools"))
import freya
from score import http, score_ledger

ap = argparse.ArgumentParser(); ap.add_argument("sim_id"); ap.add_argument("--out"); a = ap.parse_args()
STAMP = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
SNAP = KIT.parent.parent / "eval" / "sim-records" / a.sim_id / STAMP
SNAP.mkdir(parents=True, exist_ok=False)
def keep(name, data):                 # written once, as received (gzip: the calls carry the engine source in every code run)
    p = SNAP / (name + ".gz")
    p.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(p, "xt") as f:
        json.dump(data, f)
    return data
cases = {c["id"]: c for c in json.load(open(KIT / "public-test-set.json"))}
journal = {}
jp = KIT / "results" / "sim-journal.jsonl"
if jp.exists():
    for line in open(jp):
        e = json.loads(line)
        if e.get("sim_id") == a.sim_id and e.get("event") == "started":
            journal = e
sim = keep("simulation.json", freya.api("GET", f"/api/v2/simulations/{a.sim_id}")); sim = sim.get("simulation") or sim
its = keep("iterations.json", freya.api("GET", f"/api/v2/simulations/{a.sim_id}/iterations")); its = its.get("iterations") or its.get("items") or its
it = keep("iteration.json", freya.get_iteration(a.sim_id, its[0]["id"]))
calls = {r["callId"]: keep(f"calls/{r['callId']}.json", freya.get_call(r["callId"])) for r in it["runs"] if r.get("callId")}
print(f"simulation {a.sim_id} status {sim.get('status')} agent {sim.get('agentId')} retries allowed {sim.get('settings', {}).get('maxRetries')}")
rows = []
for r in it["runs"]:
    cid = (r.get("personaName") or "").split(" ")[0]
    c = cases.get(cid)
    if not c:
        continue
    cust = (journal.get("customer_ids") or {}).get(cid)
    if not cust and r.get("callId"):
        found = re.findall(r'customer_id[\\"]*[:=][\\" ]*(c_[A-Za-z0-9_\-]{6,})', json.dumps(calls[r["callId"]]))
        cust = found[0] if found else None
    led = keep(f"ledgers/{cust}.json", http("/v1/practice/ledger/" + cust)) if cust else {"calls": []}
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
summary = dict(simulation_id=a.sim_id, recovered=True, recovered_at=STAMP, records=str(SNAP.relative_to(KIT.parent.parent)), rows=rows)
keep("rows.json", summary)
if a.out:
    out = pathlib.Path(a.out)
    out = out.with_name(f"{out.stem}.{STAMP}{out.suffix or '.json'}")
    with open(out, "x") as f:
        json.dump(summary, f, indent=1)
    print("summary:", out)
print("records:", SNAP)
