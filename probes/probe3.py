import json, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from probe1 import freya, http
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from builder.compile import extraction
KIDS = extraction("id", {})
variants = {
  "n_a": [KIDS[0]],                                     # kind enum only (long description)
  "n_b": [KIDS[1]],                                     # text only
  "n_c": [{"name": "u_kind", "type": "string", "enum_values": ["answer", "refuses", "unclear", "none"], "description": "answer if the customer gives an answer to the question, refuses if they refuse, unclear otherwise", "min_confidence": 0.0},
          {"name": "u_text", "type": "string", "description": "the answer exactly as said", "min_confidence": 0.0}],
  "n_d": KIDS,
}
order = list(variants)
nodes = {}
for i, n in enumerate(order):
    nxt = order[i + 1] if i + 1 < len(order) else n
    nodes[n] = {"name": n, "node_type": "conversation", "on_enter": {"type": "tts", "text": "Question " + n + ": what is your date of birth?"},
                "task_message": "Ask for the date of birth. Do not call a tool.", "extraction_schema": variants[n],
                "transitions": [{"target_node": nxt, "description": "always", "condition": {"operator": "always"}}]}
wf = {"initial_node": "n0", "system_prompt": "Test.", "global_nodes": {}, "test_variables": {"customer_id": "c"},
      "nodes": dict(nodes, n0={"name": "n0", "node_type": "conversation", "on_enter": {"type": "tts", "text": "Hi."}, "task_message": "Say hi.",
                     "transitions": [{"target_node": "n_a", "description": "always", "condition": {"operator": "always"}}]})}
ids = freya.save_workflow("probe3", wf, state_file=os.path.join(os.path.dirname(__file__), ".probe-agents.json"))
cid = None
for m in ["Hello?", "hi", "fourteenth of March nineteen eighty-eight", "fourteenth of March nineteen eighty-eight", "fourteenth of March nineteen eighty-eight", "fourteenth of March nineteen eighty-eight"]:
    body = {"workflowId": ids["workflow_id"], "message": m, "customerVariables": {"customer_id": "c"}}
    if cid: body["callId"] = cid
    r = freya.api("POST", "/api/v2/chat/message", body); cid = r["callId"]
    print("CUST:", m, "| AGENT:", r.get("response"))
call = freya.get_call(cid)
node = None
for m in call["messages"]:
    if m.get("role") == "system":
        e = json.loads(m["message"])
        if e.get("event") == "node_enter": node = e.get("node")
        if "extract" in str(e.get("event")):
            e.pop("variable_table", None); print("  [", node, "]", json.dumps(e)[:400])
