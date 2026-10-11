"""Where an agent turn's time goes, from the platform's own call records (messages carry secondsFromStart; node
entries are system events). For each customer turn: user message -> first node entry (the talk node: extraction +
routing models), time inside the code node 'step' (engine), time inside api_* nodes (bank HTTP), and last node entry
-> the agent's reply (dialogue model). Segments the records cannot separate are reported as such.
    python3 scripts/latency.py <simulation_id> [...]"""
import json, pathlib, statistics, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "kit" / "build-the-builder"))
import freya

def segments(call):
    ms = [m for m in call.get("messages", []) if m.get("secondsFromStart") is not None]
    out, i = [], 0
    while i < len(ms):
        if ms[i]["role"] != "user":
            i += 1; continue
        t0 = ms[i]["secondsFromStart"]; j = i + 1; seg = dict(talk=0.0, code=0.0, api=0.0, reply=0.0, other=0.0)
        prev_t, prev_node = t0, "talk(user)"
        while j < len(ms) and ms[j]["role"] != "assistant":
            m = ms[j]
            if m["role"] == "system" and '"node_enter"' in (m.get("message") or ""):
                node = json.loads(m["message"]).get("node", "")
                dt = m["secondsFromStart"] - prev_t
                key = "talk" if prev_node.startswith("talk") else "code" if prev_node == "step" else "api" if prev_node.startswith("api") else "other"
                seg[key] += dt; prev_t, prev_node = m["secondsFromStart"], node
            j += 1
        if j < len(ms):
            dt = ms[j]["secondsFromStart"] - prev_t
            seg["reply" if prev_node.startswith("talk") else "other"] += dt
            seg["total"] = ms[j]["secondsFromStart"] - t0
            out.append(seg)
        i = j
    return out

def main(sims):
    allseg = []
    for sim in sims:
        its = freya.api("GET", f"/api/v2/simulations/{sim}/iterations"); its = its.get("iterations") or its.get("items") or its
        for r in freya.get_iteration(sim, its[0]["id"])["runs"]:
            if not r.get("callId"): continue
            seg = segments(freya.get_call(r["callId"]))
            allseg += seg
            if seg:
                print(f"{sim[:8]} {r['personaName'][:34]:34s} turns {len(seg):2d} median total {statistics.median(s['total'] for s in seg):5.1f}s")
    if not allseg: print("no timed turns: unknown"); return
    print(f"\nall {len(allseg)} customer turns, median seconds per segment (and share of the turn):")
    tot = statistics.median(s["total"] for s in allseg)
    for k in ("talk", "code", "api", "reply", "other"):
        med = statistics.median(s[k] for s in allseg); mean = statistics.mean(s[k] for s in allseg)
        print(f"  {k:6s} median {med:5.2f}  mean {mean:5.2f}  share of mean total {mean / statistics.mean(s['total'] for s in allseg):5.1%}")
    print(f"  total  median {tot:5.2f}  p90 {sorted(s['total'] for s in allseg)[int(0.9 * len(allseg))]:5.2f}")

if __name__ == "__main__":
    main(sys.argv[1:])
