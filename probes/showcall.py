"""Print a call transcript with per-turn extracted values and engine routing. Usage: showcall.py <call_id | persona substring>"""
import json, os, sys
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "kit", "build-the-builder"))
import freya
arg = sys.argv[1]
if len(arg) < 30:
    r = freya.api("GET", "/api/v2/simulations", workspaceId=freya.workspace_id(), limit=5)
    sims = r.get("simulations") or r.get("items") or r
    sid = sys.argv[2] if len(sys.argv) > 2 else [x for x in sims if x.get("status") == "completed"][0]["id"]; its = freya.api("GET", f"/api/v2/simulations/{sid}/iterations"); its = its.get("iterations") or its
    runs = freya.get_iteration(sid, its[0]["id"])["runs"]
    arg = [x for x in runs if arg in (x.get("personaName") or "")][0]["callId"]
call = freya.get_call(arg)
print("ended:", call.get("endedReason"))
for m in call.get("messages", []):
    role = m.get("role")
    if role in ("user", "assistant"):
        print(f"{role.upper():9} {m.get('secondsFromStart', 0):6.1f}s | {m.get('message')}")
    else:
        try: e = json.loads(m["message"])
        except Exception: continue
        if e.get("event") == "variable_extracted":
            print(f"          extracted {e['name']} = {e['value']!r}")
        elif e.get("event") == "function_call_start" and e.get("function") != "code_exec":
            print(f"          CALL {e.get('function')} {json.dumps((e.get('args') or {}).get('body'))}")
        elif e.get("event") == "function_call_complete" and e.get("function") not in ("code_exec",):
            print(f"          RESULT {json.dumps((e.get('result') or {}).get('data'))[:200]}")
        elif e.get("event") == "error":
            print("          ERROR", json.dumps(e)[:300])
        elif e.get("event") == "function_call_complete" and (e.get("result") or {}).get("validation_errors"):
            print("          validation:", e["result"]["validation_errors"])
