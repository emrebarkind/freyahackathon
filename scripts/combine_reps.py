"""Per-customer table over several simulations, from the stored snapshots (eval/sim-records/<id>/<time>/rows.json.gz,
latest snapshot of each). A customer counts only when every run passes; each run's failure reason is kept.
    python3 scripts/combine_reps.py <label>=<sim_id> [...]"""
import collections, gzip, json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
runs = [a.split("=", 1) for a in sys.argv[1:]]
table = collections.OrderedDict()
for label, sid in runs:
    snap = sorted((ROOT / "eval" / "sim-records" / sid).iterdir())[-1]
    rows = json.load(gzip.open(snap / "rows.json.gz", "rt"))["rows"]
    for r in rows:
        table.setdefault(r["id"], {})[label] = r
labels = [l for l, _ in runs]
print("| customer | " + " | ".join(labels) + " | counts |")
print("|---|" + "---|" * len(labels) + "---|")
for cid in sorted(table):
    cells, ok = [], True
    for l in labels:
        r = table[cid].get(l)
        if r is None:
            cells.append("–"); ok = False; continue
        ok &= r["pass_"]
        cells.append("pass" if r["pass_"] else "FAIL: " + "; ".join(f.split(":")[0] if f.startswith("conversation") else f for f in r["failed"])[:80])
    print(f"| {cid} | " + " | ".join(cells) + f" | {'yes' if ok else 'no'} |")
