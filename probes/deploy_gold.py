"""Compile a gold spec and save it to Freya (slot per spec), then run a scripted chat."""
import json, os, sys, time
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "kit", "build-the-builder")); sys.path.insert(0, os.path.join(ROOT, "kit", "build-the-builder", "tools"))
import freya
from score import http
from builder.compile import compile_workflow
spec_path, slot = sys.argv[1], sys.argv[2]
spec = json.load(open(spec_path)); oa = json.load(open(os.path.join(ROOT, "kit/build-the-builder/tools/openapi.json")))
wf = compile_workflow(spec, oa)
print("bytes", len(json.dumps(wf)))
freya.validate_workflow(slot, wf); print("dry-run ok")
ids = freya.save_workflow(slot, wf, state_file=os.path.join(ROOT, ".freya-agents.json")); print(json.dumps(ids))
if len(sys.argv) > 3:
    case = sys.argv[3]; msgs = sys.argv[4:]
    v = http("/v1/practice/sessions", {"case": case})["variables"]
    cid = None
    for m in msgs:
        body = {"workflowId": ids["workflow_id"], "message": m, "customerVariables": v}
        if cid: body["callId"] = cid
        t = time.time()
        try: r = freya.api("POST", "/api/v2/chat/message", body)
        except Exception as e: print("ERR", str(e)[:200]); break
        cid = r["callId"]; print(f"CUST: {m}\nAGENT ({time.time()-t:.1f}s): {r.get('response')}")
    print("ledger:", json.dumps(http("/v1/practice/ledger/" + v["customer_id"]))[:700])
    if cid:
        call = freya.get_call(cid)
        for m in call.get("messages", []):
            if m.get("role") == "system":
                try: e = json.loads(m["message"])
                except Exception: continue
                if e.get("event") in ("error",) or (e.get("event") == "function_call_complete" and (e.get("result") or {}).get("status") != "success"):
                    print("  SYS", json.dumps(e)[:400])
