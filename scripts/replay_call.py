"""Replay a recorded platform call through the current engine, locally, with no platform run.

Each customer turn is fed with exactly what the platform's extraction produced for it (the variable_extracted
events between that customer message and the next agent message), against the local generic bank holding the
case's identity and products. The engine's lines are printed next to the agent lines of the recording, and three
properties are checked over the whole call:
  * a date or amount the agent already read back (the plan) is not dropped for an earlier step;
  * the agent does not keep returning to the same question;
  * content-free turns ("please go on", "I did not catch that") stay bounded over the whole call.

    python3 scripts/replay_call.py <call.json[.gz]> <spec.json> --case PUB-13 [--extend N]
--extend N appends N more cut-off fragments after the recording ends (a customer who never finishes)."""
import argparse, collections, copy, gzip, json, pathlib, re, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from builder import selftest

ap = argparse.ArgumentParser()
ap.add_argument("call"); ap.add_argument("spec"); ap.add_argument("--case", required=True)
ap.add_argument("--openapi", default=str(ROOT / "kit" / "build-the-builder" / "tools" / "openapi.json"))
ap.add_argument("--extend", type=int, default=0)
a = ap.parse_args()

op = gzip.open if a.call.endswith(".gz") else open
rec = json.load(op(a.call, "rt")); rec = rec.get("call") or rec
case = [c for c in json.load(open(ROOT / "kit" / "build-the-builder" / "public-test-set.json")) if c["id"] == a.case][0]
spec = json.load(open(a.spec))
openapi = json.load(open(a.openapi))

# customer turns with the platform's extraction for each
turns, said, cur = [], [], None
for m in rec["messages"]:
    if m["role"] == "user":
        cur = {"text": m["message"], "x": {}}
        turns.append(cur)
    elif m["role"] == "assistant":
        said.append(m["message"]); cur = None
    elif m["role"] == "system" and cur is not None and '"variable_extracted"' in str(m["message"]):
        e = json.loads(m["message"])
        cur["x"][e["name"]] = e["value"]

def as_turn(t):
    x = t["x"]
    stage = next((k[:-5] for k in x if k.endswith("_kind")), None) or next((k[:-4] for k in x if k.endswith("_cut")), "nego")
    g = lambda f, d="": x.get(stage + f, d)
    return dict(k=g("_kind", "none"), t=g("_text") or t["text"], d=g("_date") or "", a=g("_amount") if g("_amount") not in (None, "") else "",
                f=g("_for", "none"), side=g("_side", "none"), cut=g("_cut", "no"), norm=x.get("id_norm", ""))

script = [as_turn(t) for t in turns]
last_stage_turn = dict(script[-1]) if script else {}
for i in range(a.extend):                  # the customer keeps restarting and never finishes
    script.append(dict(k="unclear", t="I have been dealing with so many emails this", d="", a="", f="none", side="none", cut="yes"))

products = [dict(p, product_id=f"p{i + 1}") for i, p in enumerate(copy.deepcopy(case["products"]))]
bank = selftest.GenericBank(json.loads(json.dumps(spec)), case["identity"], products)
V0 = dict(customer_id="c_replay", **case["variables"])
led, tr = selftest.simulate(spec, V0, bank, [dict(t) for t in script], openapi=openapi, max_steps=4000)

agent = [x[1] for x in tr if x[0] == "agent" and x[1]]
print(f"recorded agent lines {len(said)}, replayed engine lines {len(agent)}")
for i in range(max(len(said), len(agent))):
    r = said[i] if i < len(said) else ""
    e = agent[i] if i < len(agent) else ""
    mark = "  " if r[:60] == e[:60] else "≠ "
    print(f"{mark}{i:3d} rec: {r[:90]!r}\n       eng: {e[:90]!r}")

# properties over the whole call
EMPTY = re.compile(r"please go on|could you say that again|sorry\?$", re.I)   # no question in it: says nothing
empty = sum(bool(EMPTY.search(x)) for x in agent)
counts = collections.Counter(agent)
readback = next((i for i, x in enumerate(agent) if x.lower().startswith("let me read that back")), None)
plan_dates = set(re.findall(r"\b\d{1,2} [A-Z][a-z]+\b", agent[readback])) if readback is not None else set()
later_offers = [x for x in (agent[readback + 1:] if readback is not None else []) if re.search(r"could you pay", x, re.I)]
dropped = [x for x in later_offers if not any(d in x for d in plan_dates)]
print("\nledger:", {k: led[k] for k in ("promises", "notes", "outcome", "reason")}, "calls:", led["calls"])
print(f"content-free agent turns over the call: {empty} of {len(agent)}")
print("most repeated agent line:", counts.most_common(1))
print("read-back:", agent[readback][:140] if readback is not None else None)
print("offers after the read-back that drop its dates:", dropped)
