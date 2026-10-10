"""Platform probe via chat route: code-node loop, extraction overwrite/clear, re-entry speech, api_request node."""
import json, os, sys, time
KIT = os.path.join(os.path.dirname(__file__), "..", "kit", "build-the-builder")
sys.path.insert(0, KIT); sys.path.insert(0, os.path.join(KIT, "tools"))
import freya
from score import http
BANK = "https://freya-bank-mock.freyavoice.workers.dev/v1"

def code_node(name, code, nxt):
    return {"name": name, "node_type": "code", "passthrough": True, "passthrough_default_transition": nxt,
            "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
            "pre_actions": [{"type": "function", "function": {"name": "code_exec", "handler": "__function__:code_exec",
                "parameters": {"type": "object", "properties": {"code": {"type": "string", "default": code}, "timeout_ms": {"type": "number", "default": 10000}}}}}],
            "transitions": [{"target_node": nxt, "description": "always", "condition": {"operator": "always"}}]}

STEP = """try:
    c = int(vars.get('counter') or 0) + 1
    vars['counter'] = c
    vars['seen_kind'] = str(vars.get('kind'))
    vars['kind'] = ''
    vars['route'] = 'api' if vars['seen_kind'] == 'yes' else 'talk'
except Exception as e:
    vars['route'] = 'talk'
    vars['err'] = str(e)
"""
wf = {
 "initial_node": "greet",
 "system_prompt": "You are a test assistant. Speak English. One short sentence per turn.",
 "nodes": {
  "greet": {"name": "greet", "node_type": "conversation", "on_enter": {"type": "tts", "text": "Probe here. Say anything."},
            "task_message": "Ask the user whether they want to continue. Do not call a tool in this turn.",
            "extraction_schema": [{"name": "kind", "type": "string", "enum_values": ["yes", "no", "other"], "description": "yes if the user says yes, no if no, other otherwise", "min_confidence": 0.5}],
            "transitions": [{"target_node": "step", "description": "always", "condition": {"operator": "always"}}]},
  "step": code_node("step", STEP, "talk"),
  "talk": {"name": "talk", "node_type": "conversation",
           "task_message": "Tell the user exactly: counter={{counter}} seen={{seen_kind}} kind_now={{kind}}. Then ask a yes or no question. Do not call a tool.",
           "extraction_schema": [{"name": "kind", "type": "string", "enum_values": ["yes", "no", "other"], "description": "yes if the user says yes, no if no, other otherwise", "min_confidence": 0.5}],
           "transitions": [{"target_node": "step2", "description": "always", "condition": {"operator": "always"}}]},
  "step2": dict(code_node("step2", STEP, "talk"), transitions=[
            {"target_node": "call_api", "description": "api", "condition": {"logic": "or", "conditions": [{"variable": "route", "operator": "equals", "operand": "api"}]}},
            {"target_node": "talk", "description": "always", "condition": {"operator": "always"}}]),
  "call_api": {"name": "call_api", "node_type": "api_request", "passthrough": True, "passthrough_default_transition": "report",
               "on_enter": {"type": "tts", "text": "One moment please."}, "disable_inactivity_monitor": True,
               "pre_actions": [{"type": "function", "config": {"timeoutMs": 10000, "maxRetries": 0}, "function": {"name": "get_account", "handler": "__function__:api_call",
                   "parameters": {"type": "object", "properties": {"url": {"type": "string", "default": BANK + "/get_account"}, "method": {"type": "string", "default": "POST"},
                   "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                   "body": {"type": "object", "properties": {"customer_id": {"type": "string", "default": "{{customer_id}}"}}}}}}}],
               "response_mapping": [{"path": "data.error", "variable": "api_err"}, {"path": "data.ok", "variable": "api_ok"}],
               "transitions": [{"target_node": "report", "description": "always", "condition": {"operator": "always"}}]},
  "report": {"name": "report", "node_type": "conversation",
             "task_message": "Tell the user exactly: ok={{api_ok}} err={{api_err}} flat={{get_account_response.data.error}} nodeflat={{call_api_response.data.error}} fails={{call_api_failure_count}} succ={{call_api_success_count}}. Do not call a tool.",
             "transitions": []},
 },
 "global_nodes": {},
 "test_variables": {"customer_id": "c_test", "now": "2026-10-14T11:00"},
}
if __name__ == "__main__":
    print(freya.validate_workflow("probe1", wf) and "dry-run ok")
    ids = freya.save_workflow("probe1", wf, state_file=os.path.join(os.path.dirname(__file__), ".probe-agents.json"))
    print(ids)
    v = http("/v1/practice/sessions", {"case": "PUB-01"})["variables"]
    cid = None
    for msg in ["hello", "maybe", "no", "yes", "ok"]:
        t = time.time()
        r = freya.api("POST", "/api/v2/chat/message", {"workflowId": ids["workflow_id"], "message": msg, "callId": cid, "customerVariables": v} if cid else {"workflowId": ids["workflow_id"], "message": msg, "customerVariables": v})
        cid = r["callId"]
        print(f"USER: {msg!r}  ({time.time()-t:.1f}s)\nAGENT: {r.get('response')!r}")
    freya.api("POST", "/api/v2/chat/end", {"callId": cid})
    call = freya.get_call(cid)
    for m in call.get("messages", []):
        if m.get("role") == "system":
            try: e = json.loads(m["message"])
            except Exception: continue
            ev = e.get("event")
            if ev in ("node_enter", "function_call_complete", "error"):
                print("  SYS", ev, json.dumps({k: e.get(k) for k in ("node", "from_node", "function", "result", "message")})[:300])
        else:
            print(" ", m.get("role"), "|", (m.get("message") or "")[:150])
