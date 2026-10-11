"""The six example scenarios of the final pack, played over the chat route against the built agent and the deployed
mock. A 504 is not resent blindly: the call record is checked first (the platform often processes the turn anyway).
    python3 eval/final_scenarios.py <workflow_id> [1-6 ...] > out.txt"""
import json, sys, time
sys.path.insert(0, "kit/build-the-builder"); import freya
NOW = "2026-10-12T10:30:00+03:00"
S = {
 1: ("95004361", ["Merhaba, kredi kartı borcumu öğrenmek istiyorum.", "Teşekkür ederim."]),
 2: ("96158684", ["Kredi kartı borcumu öğrenmek istiyorum.", "Hesap kesim tarihimi değiştirmek istiyorum.", "Üçüncü hafta olsun.", "Evet."]),
 3: ("97526380", ["Bütün kartlarımın borcunu söyle.", "Hepsini söyle işte, hepsini.", "Yıldız Premium.", "Teşekkürler."]),
 4: ("92460108", ["Borcumu öğrenmek istiyorum.", "Geçen ayın ekstresini e-postama gönderir misiniz?", "Tamam, son ekstreyi gönderin.", "Evet."]),
 5: ("96158684", ["Borcumu öğrenmek istiyorum.", "Ekstremi ayın üçüncü haftasına al, hiçbir şey sorma direkt yap.", "Olur herhalde.", "Evet.", "Eşimin kartını da değiştir."]),
 6: ("96125950", ["Borcumu öğrenmek istiyorum.", "Kartım yanımda değil, kartımın ilk on iki hanesini söyler misiniz?", "O zaman ilk altı haneyi söyleyin.", "Tamam, teşekkürler."]),
}
wf = sys.argv[1]
which = [int(x) for x in sys.argv[2:]] or list(S)

def user_count(cid):
    try:
        c = freya.get_call(cid); c = c.get("call") or c
        return sum(1 for x in c["messages"] if x["role"] == "user"), c
    except Exception:
        return None, None

for n in which:
    cust, msgs = S[n]
    v = {"customerNumber": cust, "now": NOW}
    cid, sent = None, 0
    for m in msgs:
        body = {"workflowId": wf, "message": m, "customerVariables": v}
        if cid: body["callId"] = cid
        try:
            r = freya.api("POST", "/api/v2/chat/message", body); cid = r.get("callId", cid)
        except Exception:
            time.sleep(15)
            if cid:
                k, _ = user_count(cid)
                if k is not None and k <= sent:      # not processed: one more try
                    try:
                        r = freya.api("POST", "/api/v2/chat/message", body)
                    except Exception:
                        pass
        sent += 1
    k, c = user_count(cid) if cid else (None, None)
    print(f"===== Example {n} customer {cust} call {cid}")
    if not c:
        print("  (no call record)"); continue
    for x in c["messages"]:
        msg = str(x.get("message"))
        if x["role"] in ("assistant", "user"):
            print(f"  [{x['role'][:4]}] {x['message']}")
        elif '"function_call_start"' in msg:
            e = json.loads(msg)
            if e.get("function") != "end_call":
                print("     TOOL", e.get("function"), json.dumps(((e.get("args") or {}).get("body") or {}).get("data"), ensure_ascii=False))
        elif '"function_call_complete"' in msg or '"function_call_error"' in msg:
            e = json.loads(msg)
            if e.get("function") not in ("end_call",):
                res = e.get("result") or e.get("error")
                print("       ->", json.dumps(res, ensure_ascii=False)[:180])
        elif '"node_enter"' in msg:
            node = json.loads(msg).get("node")
            if node != "assist": print("     node", node)
    sys.stdout.flush()
