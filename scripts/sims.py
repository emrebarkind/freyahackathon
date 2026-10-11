"""Workspace simulation housekeeping (organisers' advice, 11 Oct).
    python3 scripts/sims.py                 # list the latest simulations and their status
    python3 scripts/sims.py cancel <id>     # cancel one stuck in 'running'
Do not stop run_cases.py on your side: the simulation keeps running on Freya and the next test waits for it.
A 504 from /api/v2/chat/message does not mean simulations are down."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "kit" / "build-the-builder"))
import freya

if len(sys.argv) > 2 and sys.argv[1] == "cancel":
    print(freya.cancel_simulation(sys.argv[2]))
else:
    for s in freya.list_simulations(int(sys.argv[1]) if len(sys.argv) > 1 else 10):
        s = s.get("simulation") or s
        print(s.get("id"), s.get("status"), s.get("createdAt") or s.get("created_at") or "", s.get("name", ""))
