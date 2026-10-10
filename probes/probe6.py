"""Probe 6: api nodes WITHOUT pre_process_code: number typing of amount, reason omitted, timing."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from probe1 import code_node, freya, http, BANK

def api(name, tool, body, nxt, numtype=False):
    props = {"customer_id": {"type": "string", "default": "{{customer_id}}"}}
    for k, v in body.items():
        props[k] = {"type": "number" if (numtype and k == "amount") else "string", "default": v}
    return {"name": name, "node_type": "api_request", "passthrough": True, "passthrough_default_transition": nxt,
            "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
            "pre_actions": [{"type": "function", "config": {"timeoutMs": 10000, "maxRetries": 0}, "function": {"name": tool, "handler": "__function__:api_call",
                "parameters": {"type": "object", "properties": {"url": {"type": "string", "default": f"{BANK}/{tool}"}, "method": {"type": "string", "default": "POST"},
                "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                "body": {"type": "object", "properties": props}}}}}],
            "transitions": [{"target_node": nxt, "description": "always", "condition": {"operator": "always"}}]}

SETUP = """vars['f1'] = 'date_of_birth'
vars['a1'] = '1988-03-14'
vars['f2'] = 'phone_last4'
vars['a2'] = '4471'
vars['p_amount'] = 420.0
vars['p_date'] = '2026-10-14'
vars['c_outcome'] = 'promise'
"""
wf = {"initial_node": "talk", "system_prompt": "Test.", "global_nodes": {}, "test_variables": {"customer_id": "c"},
 "nodes": {
  "talk": {"name": "talk", "node_type": "conversation", "on_enter": {"type": "tts", "text": "Say go."}, "task_message": "Say go.",
           "transitions": [{"target_node": "setup", "description": "always", "condition": {"operator": "always"}}]},
  "setup": code_node("setup", SETUP, "v1"),
  "v1": api("v1", "verify_identity", {"field": "{{f1}}", "answer": "{{a1}}"}, "v2"),
  "v2": api("v2", "verify_identity", {"field": "{{f2}}", "answer": "{{a2}}"}, "acc"),
  "acc": api("acc", "get_account", {}, "pr"),
  "pr": api("pr", "create_promise", {"product_id": "p1", "amount": "{{p_amount}}", "date": "{{p_date}}"}, "cl", numtype=True),
  "cl": api("cl", "close_call", {"outcome": "{{c_outcome}}", "reason": "{{c_reason_unset}}"}, "done"),
  "done": {"name": "done", "node_type": "conversation", "on_enter": {"type": "tts", "text": "Done."}, "task_message": "Say done.", "transitions": []},
 }}
ids = freya.save_workflow("probe6", wf, state_file=os.path.join(os.path.dirname(__file__), ".probe-agents.json"))
v = http("/v1/practice/sessions", {"case": "PUB-01"})["variables"]
cid = None
for m in ["Hello?", "go"]:
    body = {"workflowId": ids["workflow_id"], "message": m, "customerVariables": v}
    if cid: body["callId"] = cid
    r = freya.api("POST", "/api/v2/chat/message", body); cid = r["callId"]; print(m, "->", r.get("response"))
led = http("/v1/practice/ledger/" + v["customer_id"])
print(json.dumps({k: led[k] for k in ("promises", "outcome", "reason")}))
for c in led["calls"]: print(c["tool"], json.dumps(c["args"]), c["status"])
call = freya.get_call(cid)
for m in call["messages"]:
    if m.get("role") == "system":
        e = json.loads(m["message"])
        if e.get("event") in ("node_enter", "function_call_start", "function_call_complete"):
            print(f"{m.get('secondsFromStart', 0):6.2f}", e.get("event"), e.get("node") or e.get("function"))
