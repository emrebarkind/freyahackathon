"""Probe 2: tts from code var, clearing string/float vars, get_account list shape in vars, close sequence."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from probe1 import code_node, freya, http, BANK

def api_node(name, tool, body, nxt, mapping, tts=None):
    props = {"customer_id": {"type": "string", "default": "{{customer_id}}"}}
    props.update({k: {"type": "string", "default": v} for k, v in body.items()})
    return {"name": name, "node_type": "api_request", "passthrough": True, "passthrough_default_transition": nxt,
            "on_enter": {"type": "tts", "text": tts} if tts else {"type": "silent"}, "disable_inactivity_monitor": True,
            "pre_actions": [{"type": "function", "config": {"timeoutMs": 10000, "maxRetries": 0}, "function": {"name": tool, "handler": "__function__:api_call",
                "parameters": {"type": "object", "properties": {"url": {"type": "string", "default": f"{BANK}/{tool}"}, "method": {"type": "string", "default": "POST"},
                "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                "body": {"type": "object", "properties": props}}}}}],
            "response_mapping": mapping, "transitions": [{"target_node": nxt, "description": "always", "condition": {"operator": "always"}}]}

STEP = r"""
import json
try:
    st = vars.get('st') or 'start'
    log = []
    log.append('ans=' + repr(vars.get('u_answer')) + ' amt=' + repr(vars.get('u_amount')))
    if st == 'start':
        vars['say'] = 'Probe two. Tell me your date of birth.'
        vars['st'] = 'dob'; vars['next'] = 'talk'
    elif st == 'dob':
        vars['q_field'] = 'date_of_birth'; vars['q_answer'] = '1988-03-14'
        vars['st'] = 'phone'; vars['next'] = 'verify'
        vars['u_answer'] = ''; vars['u_amount'] = ''
    elif st == 'phone':
        vars['say'] = 'Verified=' + str(vars.get('verify_verified')) + '. Now the last four digits please.'
        vars['st'] = 'phone2'; vars['next'] = 'talk'
    elif st == 'phone2':
        vars['q_field'] = 'phone_last4'; vars['q_answer'] = '4471'
        vars['st'] = 'acct'; vars['next'] = 'verify'
    elif st == 'acct':
        vars['st'] = 'show'; vars['next'] = 'account'
    elif st == 'show':
        p = vars.get('acct_products')
        keys = sorted(k for k in vars.keys() if 'product' in k)[:12]
        vars['dbg'] = 'type=' + type(p).__name__ + ' val=' + str(p)[:200] + ' keys=' + ','.join(keys)
        vars['say'] = 'Debug ready. Say anything.'
        vars['st'] = 'bye'; vars['next'] = 'talk'
    else:
        vars['say'] = 'Thank you, goodbye.'
        vars['c_outcome'] = 'no_promise'; vars['c_reason'] = 'refused'
        vars['next'] = 'close'
    vars['dbglog'] = ' | '.join(log)
except Exception as e:
    vars['say'] = 'error ' + str(e)[:100]; vars['next'] = 'talk'
"""
STEP = STEP.replace("{", "{ ").replace("}", " }") if "{{" in STEP else STEP
routes = ["talk", "verify", "account", "close"]
step = code_node("step", STEP, "talk")
step["transitions"] = [{"target_node": r, "description": r, "condition": {"logic": "or", "conditions": [{"variable": "next", "operator": "equals", "operand": r}]}} for r in routes] + \
                      [{"target_node": "talk", "description": "always", "condition": {"operator": "always"}}]
wf = {
 "initial_node": "step",
 "system_prompt": "You are a test assistant.",
 "nodes": {
  "step": step,
  "talk": {"name": "talk", "node_type": "conversation", "on_enter": {"type": "tts", "text": "{{say}}"},
           "task_message": "Say only: {{say}}. Do not call a tool.",
           "extraction_schema": [
               {"name": "u_answer", "type": "string", "description": "The security answer the user just gave, verbatim. Empty if none.", "min_confidence": 0.5},
               {"name": "u_amount", "type": "float", "description": "An amount of money the user just said, as a number. Empty if none.", "min_confidence": 0.5}],
           "transitions": [{"target_node": "step", "description": "always", "condition": {"operator": "always"}}]},
  "verify": api_node("verify", "verify_identity", {"field": "{{q_field}}", "answer": "{{q_answer}}"}, "step",
                     [{"path": "data.ok", "variable": "verify_ok"}, {"path": "data.verified", "variable": "verify_verified"}, {"path": "data.all_verified", "variable": "verify_all"}]),
  "account": api_node("account", "get_account", {}, "step", [{"path": "data.products", "variable": "acct_products"}, {"path": "data.ok", "variable": "acct_ok"}]),
  "close": dict(api_node("close", "close_call", {"outcome": "{{c_outcome}}", "reason": "{{c_reason}}"}, "end", [], tts="{{say}}")),
  "end": {"name": "end", "node_type": "end_call", "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True, "transitions": [],
          "terminal": {"type": "function", "function": {"name": "probe_end", "handler": "__function__:end_call", "parameters": {"type": "object", "properties": {"message_mode": {"type": "string", "default": "none"}}}}}},
 },
 "global_nodes": {},
 "test_variables": {"customer_id": "c_test", "now": "2026-10-14T11:00"},
}
if __name__ == "__main__":
    ids = freya.save_workflow("probe2", wf, state_file=os.path.join(os.path.dirname(__file__), ".probe-agents.json"))
    print(ids)
    v = http("/v1/practice/sessions", {"case": "PUB-01"})["variables"]
    cid = None
    for msg in ["hello", "hello again", "fourteenth of March 1988, and I owe four hundred twenty", "ok", "four four seven one", "fine", "bye"]:
        body = {"workflowId": ids["workflow_id"], "message": msg, "customerVariables": v}
        if cid: body["callId"] = cid
        t = time.time()
        try: r = freya.api("POST", "/api/v2/chat/message", body)
        except Exception as e: print("ERR", str(e)[:100]); break
        cid = r["callId"]
        print(f"USER: {msg!r} ({time.time()-t:.1f}s)\nAGENT: {r.get('response')!r} ended={r.get('endedByAgent')}")
    call = freya.get_call(cid)
    last_vt = None
    for m in call.get("messages", []):
        if m.get("role") == "system":
            try: e = json.loads(m["message"])
            except Exception: continue
            if e.get("event") in ("function_call_complete", "error", "node_enter"):
                print("  SYS", e.get("event"), json.dumps({k: e.get(k) for k in ("node", "function", "result", "message", "details")})[:260])
            if e.get("variable_table"): last_vt = e["variable_table"]
        else:
            print(" ", m.get("role"), "|", (m.get("message") or "")[:200])
            ws = m.get("workflowSnapshot") or {}
            if ws.get("variableTable"): last_vt = ws["variableTable"]
    if last_vt:
        for k in sorted(last_vt):
            if any(s in k for s in ("dbg", "u_", "acct", "verify_", "products")):
                print("  VT", k, "=", json.dumps(last_vt[k])[:220])
    print("ledger:", json.dumps(http("/v1/practice/ledger/" + v["customer_id"]))[:500])
