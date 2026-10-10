import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from probe1 import freya, code_node
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from builder.compile import extraction
KIDS = extraction("id", {})
def talk(n, nxt, schema): return {"name": n, "node_type": "conversation", "on_enter": {"type": "tts", "text": "Node " + n + ": date of birth?"},
    "task_message": "Ask for the date of birth.", "extraction_schema": schema,
    "transitions": [{"target_node": nxt, "description": "always", "condition": {"operator": "always"}}]}
nodes = {
 "n0": talk("n0", "c1", []),
 "c1": code_node("c1", "vars['u_kind'] = 'none'\nvars['u_text'] = ''\n_PAD = " + repr("x" * 90000) + "\n", "t_both"),        # both cleared by code
 "t_both": talk("t_both", "c2", KIDS),
 "c2": code_node("c2", "vars['u_kind'] = 'none'\n", "t_kindonly_cleared"),                 # only kind cleared
 "t_kindonly_cleared": talk("t_kindonly_cleared", "c3", KIDS),
 "c3": code_node("c3", "vars['u_text'] = 'x'\nvars['u_kind'] = 'none'\n", "t_textx"),       # text set to non-empty
 "t_textx": talk("t_textx", "c4", KIDS),
 "c4": code_node("c4", "vars.pop('u_text', None)\nvars.pop('u_kind', None)\n", "t_popped"), # popped
 "t_popped": talk("t_popped", "t_popped", KIDS),
}
wf = {"initial_node": "n0", "system_prompt": "Test.", "global_nodes": {}, "test_variables": {"customer_id": "c"}, "nodes": nodes}
ids = freya.save_workflow("probe5", wf, state_file=os.path.join(os.path.dirname(__file__), ".probe-agents.json"))
cid = None
for m in ["Hello?", "hi", "fourteenth of March nineteen eighty-eight", "the second of May 1990", "four four seven one", "twelve July 1991", "end"]:
    body = {"workflowId": ids["workflow_id"], "message": m, "customerVariables": {"customer_id": "c"}}
    if cid: body["callId"] = cid
    r = freya.api("POST", "/api/v2/chat/message", body); cid = r["callId"]
    print("CUST:", m, "| AGENT:", r.get("response"))
call = freya.get_call(cid); node = None
for m in call["messages"]:
    if m.get("role") == "system":
        e = json.loads(m["message"])
        if e.get("event") == "node_enter": node = e.get("node")
        if "extract" in str(e.get("event")) or e.get("event") == "error":
            e.pop("variable_table", None); print("  [", node, "]", json.dumps(e)[:300])
        if e.get("event") == "function_call_complete" and (e.get("result") or {}).get("validation_errors"):
            print("  [", node, "] validation:", e["result"]["validation_errors"])
