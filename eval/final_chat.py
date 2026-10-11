"""Chat-route check of the final agent against the deployed mock: a scripted Turkish conversation; prints the
agent's replies and every tool call (url, body, status).  python3 eval/final_chat.py <workflow_id> <customerNo> <msg> [msg...]"""
import json, sys, time
sys.path.insert(0, "kit/build-the-builder"); import freya
wf, cust, msgs = sys.argv[1], sys.argv[2], sys.argv[3:]
v = {"customerNumber": cust, "now": "2026-10-12T10:30:00+03:00"}
cid = None
for m in msgs:
    body = {"workflowId": wf, "message": m, "customerVariables": v}
    if cid: body["callId"] = cid
    for k in range(3):
        try:
            r = freya.api("POST", "/api/v2/chat/message", body); break
        except Exception as e:
            print("   (chat error:", str(e)[:80], ")"); time.sleep(5); r = {}
    cid = r.get("callId", cid)
    print("U:", m); print("A:", (r.get("response") or "")[:400])
try:
    c = freya.get_call(cid); c = c.get("call") or c
    for x in c["messages"]:
        msg = str(x.get("message"))
        if "function_call" in msg or "node_enter" in msg:
            e = json.loads(x["message"])
            if e.get("event") == "node_enter": print("   node", e.get("node")); continue
            a = e.get("args") or {}
            print("   ", e.get("event"), e.get("function"), str(a.get("url", ""))[-40:], json.dumps(a.get("body"), ensure_ascii=False)[:200], json.dumps(e.get("result") or e.get("error"), ensure_ascii=False)[:160])
except Exception as e:
    print("call fetch failed", e)
