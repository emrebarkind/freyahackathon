"""The six example scenarios of the final pack, played over the chat route against the built agent and the deployed
mock. A 504 is not resent blindly: the call record is checked first (the platform often processes the turn anyway).
    python3 eval/final_scenarios.py <workflow_id> [1-6 ...] > out.txt"""
import json, sys, time
sys.path.insert(0, "kit/build-the-builder"); import freya
N = "2026-10-12T10:30:00+03:00"
S = {
 1: ("93075404", ["Borcumu öğrenmek istiyorum.", "Bir dört sıfır iki.", "Teşekkürler."], N),
 2: ("92030487", ["Yıldız Pratik kartımın borcunu öğrenmek istiyorum.", "Dört iki beş üç.", "Bilmiyorum, kartım yanımda değil.", "Tamam."], N),
 3: ("93821776", ["Borcumu öğrenmek istiyorum."], N),
 4: ("97073972", ["Borcumu öğrenmek istiyorum."], N),
 5: ("95813998", ["Borcumu öğrenmek istiyorum.", "Yıldız Prestij.", "Yıldız Fly.", "Teşekkürler."], N),
 6: ("94907600", ["Borcumu öğrenmek istiyorum.", "Teşekkürler."], N),
 7: ("97631186", ["Borcumu öğrenmek istiyorum.", "Teşekkürler."], N),
 8: ("94339861", ["Borcumu öğrenmek istiyorum.", "Hesap kesim tarihimi değiştirmek istiyorum.", "Dördüncü hafta."], N),
 9: ("93635512", ["Yıldız Platinum kartımın borcunu öğrenmek istiyorum.", "Ekstremi e-postama gönderin.", "Evet."], N),
 10: ("92335586", ["Borcumu öğrenmek istiyorum.", "Teşekkürler."], N),
 11: ("95004361", ["Hi, I would like to know my credit card debt."], N),
 12: ("95004361", ["Borcumu öğrenmek istiyorum.", "Bu borcu nasıl ödeyebilirim?"], N),
 13: ("96158684", ["Borcumu öğrenmek istiyorum.", "Bu borç yanlış, ben ödeme yapmıştım."], N),
 14: ("97116902", ["Kartımın faiz oranı ne kadar?", "Hayır, borcumu öğrenmek istiyorum.", "Yıldız Fly.", "Teşekkürler."], N),
 15: ("95960044", ["Yıldız Pratik kartımın borcunu öğrenmek istiyorum.", "Teşekkürler."], "2026-10-16T10:30:00+03:00"),
 16: ("95004361", ["Borcumu öğrenmek istiyorum.", "Teşekkürler."], "2026-10-20T10:30:00+03:00"),
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
    cust, msgs, NOW = S[n]
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
