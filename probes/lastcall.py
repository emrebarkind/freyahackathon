import json, os, sys
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "kit", "build-the-builder"))
import freya
wid = sys.argv[1]
r = freya.api("GET", "/api/v2/call", workspaceId=freya.workspace_id(), limit=5)
calls = r.get("calls") or r.get("items") or r
c = calls[0] if isinstance(calls, list) else None
cid = c["id"]
call = freya.get_call(cid)
keys = sys.argv[2].split(",") if len(sys.argv) > 2 else ["u_kind", "u_text", "u_date", "u_amount", "next", "engine_error"]
for m in call.get("messages", []):
    role = m.get("role")
    if role in ("user", "assistant"):
        print(role.upper(), "|", (m.get("message") or "")[:160])
        vt = (m.get("workflowSnapshot") or {}).get("variableTable") or {}
        if vt: print("   VT", {k: (vt[k].get("value") if isinstance(vt[k], dict) else vt[k]) for k in keys if k in vt})
    else:
        try: e = json.loads(m["message"])
        except Exception: continue
        if e.get("event") in ("extraction_complete", "extraction", "variables_extracted", "error") or "extract" in str(e.get("event")):
            print("  SYS", json.dumps(e)[:500])
        if e.get("event") == "route_evaluated":
            vt = e.get("variable_table") or {}
            print("  ROUTE", e.get("from_node"), "->", e.get("target"), {k: (vt[k].get("value") if isinstance(vt.get(k), dict) else vt.get(k)) for k in keys if k in vt})
