"""Probe 7: what makes the step code node slow? tiny vs big literal vs real engine exec."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from probe1 import code_node, freya
from builder.compile import engine_source
spec = json.load(open(os.path.join(os.path.dirname(__file__), "..", "submission", "brief-a.spec.json")))
eng = engine_source(spec)
body_only = eng.split("_SRC = ", 1)[1].split("\nexec(", 1)[0]
codes = {
  "c_tiny": "vars['x'] = 1\n",
  "c_bigliteral": "_S = " + repr("x" * 90000) + "\nvars['y'] = len(_S)\n",
  "c_compile_only": "_SRC = " + body_only + "\n_c = compile(_SRC, 'e', 'exec')\nvars['z'] = 1\n",
  "c_engine": eng,
}
order = list(codes)
nodes = {"talk": {"name": "talk", "node_type": "conversation", "on_enter": {"type": "tts", "text": "go"}, "task_message": "Say go.",
                  "transitions": [{"target_node": order[0], "description": "always", "condition": {"operator": "always"}}]}}
for i, k in enumerate(order):
    nodes[k] = code_node(k, codes[k], order[i + 1] if i + 1 < len(order) else "done")
nodes["done"] = {"name": "done", "node_type": "conversation", "on_enter": {"type": "tts", "text": "{{say}}"}, "task_message": "Say done.", "transitions": []}
wf = {"initial_node": "talk", "system_prompt": "Test.", "global_nodes": {}, "test_variables": {"customer_id": "c", "first_name": "A", "last_name": "B", "title": "Mr", "now": "2026-10-14T11:00", "open_kind": "confirmed"}, "nodes": nodes}
ids = freya.save_workflow("probe7", wf, state_file=os.path.join(os.path.dirname(__file__), ".probe-agents.json"))
cid = None
for m in ["Hello?", "go"]:
    body = {"workflowId": ids["workflow_id"], "message": m, "customerVariables": {"customer_id": "c", "first_name": "A", "last_name": "B", "title": "Mr", "now": "2026-10-14T11:00"}}
    if cid: body["callId"] = cid
    r = freya.api("POST", "/api/v2/chat/message", body); cid = r["callId"]; print(m, "->", r.get("response"))
call = freya.get_call(cid); t0 = None
for m in call["messages"]:
    if m.get("role") == "system":
        e = json.loads(m["message"])
        if e.get("event") in ("function_call_start", "function_call_complete", "node_enter"):
            print(f"{m.get('secondsFromStart', 0):6.2f}", e.get("event"), e.get("node") or e.get("function"), (e.get("result") or {}).get("validation_errors", ""))
