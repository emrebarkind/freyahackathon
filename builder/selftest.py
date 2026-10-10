"""Self-tests a builder run can afford inside its time budget:
  * run_all: the in-agent engine against synthetic customers derived from the spec, with a generic fake bank.
  * chat_smoke: a few turns over Freya's chat route to prove the published workflow starts and speaks.
"""
import copy
import datetime
import json
import random
import re

from builder.runtime import cal, engine

API_SLOTS = {
    "api_verify": ("verify_identity", ["q_field", "q_answer"]),
    "api_account": ("get_account", []),
    "api_promise": ("create_promise", ["p_product", "p_amount", "p_date"]),
    "api_note": ("add_note", ["n_product", "n_reason"]),
    "api_callback": ("schedule_callback", ["cb_date", "cb_time", "cb_datetime"]),
    "api_transfer": ("transfer_to_agent", ["t_queue"]),
    "api_close": ("close_call", ["c_outcome", "c_reason"]),
    "api_close_nr": ("close_call", ["c_outcome"]),
}


class GenericBank:
    def __init__(self, spec, identity, products, faults=None):
        self.spec, self.identity, self.products = spec, identity, products
        self.faults = dict(faults or {})
        self.R = spec["identity"].get("response", {})
        self.led = dict(promises=[], notes=[], callbacks=[], transfers=[], outcome=None, reason=None, calls=[])
        self.ok_fields, self.wrong = set(), 0

    def ok(self, tool):
        """The success flag in the shape the spec expects for this tool (e.g. ok: true, status: 'created')."""
        r = self.spec.get("responses", {}).get(tool) or {"field": "ok", "values": ["true"]}
        if not r.get("field"):
            return {}
        v = (r.get("values") or ["true"])[0]
        return {r["field"]: True if str(v).lower() == "true" else v}

    def verdict(self, good):
        pv = self.R.get("pass_values")
        if pv:
            return pv[0] if good else "fail"
        return bool(good)

    def call(self, tool, a):
        self.led["calls"].append(tool)
        if self.faults.get(tool, 0) > 0:
            self.faults[tool] -= 1
            return None
        R = self.R
        if tool == "verify_identity":
            if str(a["q_answer"]) == str(self.identity.get(a["q_field"])):
                self.ok_fields.add(a["q_field"])
                return {R.get("ok", "ok"): True, R.get("verified", "verified"): self.verdict(True),
                        R.get("all_verified", "all_verified"): self.verdict(len(self.ok_fields) == len(self.identity)),
                        R.get("left", "wrong_answers_left"): self.spec["identity"].get("max_wrong", 3) - self.wrong}
            self.wrong += 1
            return {R.get("ok", "ok"): True, R.get("verified", "verified"): self.verdict(False), R.get("all_verified", "all_verified"): self.verdict(False),
                    R.get("left", "wrong_answers_left"): self.spec["identity"].get("max_wrong", 3) - self.wrong}
        if tool == "get_account":
            return dict(self.ok(tool), **{self.spec["products"].get("list_field", "products"): copy.deepcopy(self.products)})
        if tool == "create_promise":
            self.led["promises"].append((a["p_product"], round(float(a["p_amount"]), 2), a["p_date"]))
        elif tool == "add_note":
            self.led["notes"].append((a["n_product"], a["n_reason"]))
        elif tool == "schedule_callback":
            self.led["callbacks"].append((a.get("cb_date") or str(a.get("cb_datetime", ""))[:10],
                                          a.get("cb_time") or str(a.get("cb_datetime", ""))[11:16]))
        elif tool == "transfer_to_agent":
            self.led["transfers"].append(a["t_queue"])
        elif tool == "close_call":
            self.led["outcome"], self.led["reason"] = a["c_outcome"], a.get("c_reason") or ""
        return dict(self.ok(tool), done=True)


def flatten(prefix, obj, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            flatten(prefix + "." + k, v, out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            flatten(prefix + "." + str(i), v, out)
    else:
        out[prefix] = "true" if obj is True else "false" if obj is False else obj


def simulate(spec, variables, bank, turns, max_steps=300):
    """turns: list of dicts k/t/d/a/s (what extraction would produce). Returns (ledger, transcript)."""
    engine.S = spec
    cal.P = dict(workdays=spec["calendar"]["workdays"], holidays=spec["calendar"]["holidays"])
    V = dict(variables)
    turns = list(turns)
    tr = []

    def feed(stage, u):
        V.update({stage + "_kind": u.get("k", "none"), stage + "_text": u.get("t", ""), stage + "_date": u.get("d", ""),
                  stage + "_amount": u.get("a", ""), stage + "_scope": u.get("s", "none"), stage + "_side": u.get("side", "none"),
                  stage + "_for": u.get("f", "none"), stage + "_cut": u.get("cut", "no")})

    tr.append(("agent", "<opening>"))
    feed("open", turns.pop(0))
    for _ in range(max_steps):
        engine.main(V)
        if V.get("engine_error"):
            raise RuntimeError("engine error: " + V["engine_error"])
        nxt = V.get("next")
        if nxt in API_SLOTS:
            tool, slots = API_SLOTS[nxt]
            if nxt in ("api_close", "api_close_nr"):
                tr.append(("agent", V.get("say", "")))
            for k in [k for k in V if k.startswith(nxt + "_response.")]:
                del V[k]
            r = bank.call(tool, {s: V.get(s) for s in slots})
            if r is not None:
                flatten(nxt + "_response.data", r, V)
            allv = spec["identity"].get("response", {}).get("all_verified")
            if nxt == "api_verify" and allv and str(V.get("api_verify_response.data." + allv)).lower() == "true":
                for k in [k for k in V if k.startswith("api_account_response.")]:
                    del V[k]
                r = bank.call("get_account", {})            # the workflow's direct transition verify -> account
                if r is not None:
                    flatten("api_account_response.data", r, V)
            if nxt in ("api_close", "api_close_nr"):
                break
            continue
        if nxt and nxt.startswith("talk_"):
            tr.append(("agent", V.get("say", "")))
            if not turns and nxt == "talk_after":
                turns = [dict(k="done", t="no, that's all, thank you")]
            if not turns:
                tr.append(("customer", "<silence>"))
                break
            u = turns.pop(0)
            tr.append(("customer", json.dumps(u)))
            feed(nxt[5:].replace("open_again", "open"), u)
            continue
        break
    return bank.led, tr


# ------------------------------------------------------------------------------------------ synthetic data
def pick_now(spec):
    d = datetime.date(2026, 10, 14)
    cal.P = dict(workdays=spec["calendar"]["workdays"], holidays=spec["calendar"]["holidays"])
    while not cal.is_business_day(d):
        d += datetime.timedelta(days=1)
    return d


SPOKEN = {"date": "the twenty-first of June nineteen eighty-five", "year": "nineteen eighty-five", "upper": "it's A B one two, C D",
          "text": "it's Smith", "email": "alex dot morgan at example dot com"}


def identity_values(spec):
    vals, wrong = {}, {}
    for q in spec["identity"]["questions"]:
        k = q.get("kind")
        if k == "date":
            fmt = q.get("format") or "%Y-%m-%d"
            vals[q["field"]], wrong[q["field"]] = datetime.date(1985, 6, 21).strftime(fmt), datetime.date(1979, 2, 3).strftime(fmt)
        elif k == "email":
            vals[q["field"]], wrong[q["field"]] = "alex.morgan@example.com", "x@y.com"
        elif k == "digits":
            n = int(q.get("length") or 4)
            vals[q["field"]], wrong[q["field"]] = "7" * n, "3" * n
        elif k == "year":
            vals[q["field"]], wrong[q["field"]] = "1985", "1971"
        elif k == "upper":
            vals[q["field"]], wrong[q["field"]] = "AB12CD", "ZZ99ZZ"
        else:
            vals[q["field"]], wrong[q["field"]] = "Smith", "Jones"
    return vals, wrong


def make_product(spec, i, typ, days_late):
    P_ = spec["products"]
    p = {P_.get("id_field", "product_id"): "p%d" % (i + 1), P_.get("type_field", "type"): typ, P_.get("days_field", "days_late"): days_late,
         "card_last4": "4821", "account_last4": "1234", "last4": "1234"}
    full = 300.0 + 100 * i
    p[spec["products"].get("amount_field", "past_due")] = full
    ff = spec["products"].get("floor_field", {}).get(typ)
    if ff:
        p[ff] = round(full * 0.3, 2)
    return p


def expected(spec, event, promises=(), notes=(), callbacks=(), transfers=()):
    e = spec["events"][event]
    return dict(outcome=e.get("outcome"), reason=e.get("reason") or "", promises=sorted(promises), notes=sorted(notes),
                callbacks=sorted(callbacks), transfers=sorted(transfers))


def run_all(spec, openapi):
    out = []
    try:
        today = pick_now(spec)
        V0 = dict(customer_id="c_test", first_name="Alex", last_name="Morgan", title="Mr", now=today.isoformat() + "T11:00")
        ident, wrong = identity_values(spec)
        types = list(spec["products"]["names"].keys()) or ["product"]
        bands = spec["bands"]
        dl0 = int(bands[0].get("min", 1))
        single = [make_product(spec, 0, types[0], dl0)]
        C = dict(k="confirmed", t="yes that's me")
        answers = [dict(k="answer", t=ident[q["field"]]) for q in spec["identity"]["questions"]]
        notes_on = spec.get("notes", {}).get("enabled")
        T = spec["events"]["transfer_support"].get("queue")
        R = spec["events"]["transfer_restructuring"].get("queue")
        ev_ = spec["events"]

        def notes_for(event, pids=("p1",)):
            n = ev_.get(event, {}).get("note")
            return [(p, n) for p in pids] if notes_on and n else []
        spoken = [dict(k="answer", t=SPOKEN.get(q.get("kind"), " ".join("seven" for _ in range(int(q.get("length") or 4)))))
                  for q in spec["identity"]["questions"]]
        full = single[0][spec["products"].get("amount_field", "past_due")]
        cb = spec["callback"]
        nb = cal.next_business_day(today, include_self=False)
        start_h = int(cb.get("start", "10:00")[:2])
        cb_time = "%02d:00" % min(start_h + 1, int(cb.get("end", "19:00")[:2]))
        scenarios = [
            ("happy path, pays in full today", [C] + answers + [dict(k="yes"), dict(k="yes")], single,
             expected(spec, "promise", promises=[("p1", full, today.isoformat())])),
            ("someone else answers, books a callback", [dict(k="third_party"), dict(k="gives_time", t="next business day at %s" % cb_time, d=nb.isoformat())], single,
             expected(spec, "callback", callbacks=[(nb.isoformat(), cb_time)])),
            ("wrong number", [dict(k="wrong_number")], single, expected(spec, "wrong_number")),
            ("identity fails", [C] + [dict(k="answer", t=wrong[spec["identity"]["questions"][0]["field"]])] * int(spec["identity"].get("max_wrong", 3)), single,
             expected(spec, "id_failed")),
            ("identity answered the way people speak", [C] + spoken + [dict(k="yes"), dict(k="yes")], single,
             expected(spec, "promise", promises=[("p1", full, today.isoformat())])),
            ("already paid", [C] + answers + [dict(k="already_paid")], single, expected(spec, "paid", notes=notes_for("paid"))),
            ("dispute", [C] + answers + [dict(k="dispute")], single, expected(spec, "dispute", notes=notes_for("dispute"))),
            ("hardship, accepts support" if T else "hardship (no transfer in this brief)", [C] + answers + [dict(k="hardship"), dict(k="yes")], single,
             expected(spec, "transfer_support", transfers=[T]) if T else expected(spec, "hardship", notes=notes_for("hardship"))),
            ("restructuring request", [C] + answers + [dict(k="restructure")], single,
             expected(spec, "transfer_restructuring", transfers=[R] if R else [], notes=[] if R else notes_for("transfer_restructuring"))),
            ("flat refusals", [C] + answers + [dict(k="no")] * 6, single, expected(spec, "refused", notes=notes_for("refused"))),
            ("the bank fails to record the promise twice", [C] + answers + [dict(k="yes"), dict(k="yes")], single,
             expected(spec, "service_error", notes=notes_for("service_error")), dict(create_promise=2)),
            ("the callback booking fails once, then works", [dict(k="third_party"), dict(k="gives_time", t="next business day at %s" % cb_time, d=nb.isoformat())], single,
             expected(spec, "callback", callbacks=[(nb.isoformat(), cb_time)]), dict(schedule_callback=1)),
        ]
        if len(types) > 1:
            multi = [make_product(spec, i, t, dl0) for i, t in enumerate(types[:3])]
            fri = cal.ladder_date(today, "last_business_day_this_week", None) if False else None
            idf = spec["products"].get("id_field", "product_id")
            prom = [(p[idf], p[spec["products"].get("amount_field", "past_due")], today.isoformat()) for p in multi]
            scenarios.append(("several products, all paid today", [C] + answers + [dict(k="yes"), dict(k="yes")], multi,
                              expected(spec, "promise", promises=prom)))
        for sc in scenarios:
            name, turns, prods, exp = sc[:4]
            try:
                bank = GenericBank(spec, ident, copy.deepcopy(prods), sc[4] if len(sc) > 4 else None)
                led, tr = simulate(spec, V0, bank, turns)
                got = dict(outcome=led["outcome"], reason=led["reason"] or "", promises=sorted(led["promises"]), notes=sorted(led["notes"]),
                           callbacks=sorted(led["callbacks"]), transfers=sorted(led["transfers"]))
                spoken = " ".join(t for w, t in tr if w == "agent")
                leaked = [x for x in re.findall(r"\{[a-z_]+\}", spoken)]
                ok = got == exp and led["calls"] and led["calls"][-1] == "close_call" and not leaked
                detail = "" if ok else (f"unfilled placeholders {leaked}; " if leaked else "") + f"got {got} expected {exp}; transcript: " + " | ".join(f"{w}: {t}" for w, t in tr)[:1500]
                out.append((name, bool(ok), detail))
            except Exception as e:
                out.append((name, False, f"{type(e).__name__}: {e}"))
    except Exception as e:
        out.append(("setup", False, f"{type(e).__name__}: {e}"))
    return out


def chat_smoke(freya, workflow_id, spec):
    """The published workflow starts, speaks the opening logic and handles a third party without bank calls."""
    out = []
    v = dict(customer_id="c_smoke_test", first_name="Alex", last_name="Morgan", title="Mr", now="2026-10-14T11:00")
    try:
        cid = None
        replies = []
        for m in ["Hello?", "Sorry, who is this?", "No, this is her brother, she is not home."]:
            body = {"workflowId": workflow_id, "message": m, "customerVariables": v}
            if cid:
                body["callId"] = cid
            r = freya.api("POST", "/api/v2/chat/message", body)
            cid = r.get("callId", cid)
            replies.append(r.get("response", ""))
        try:
            freya.api("POST", "/api/v2/chat/end", {"callId": cid})
        except Exception:
            pass
        out.append(("workflow answers over chat", all(replies), " / ".join(replies)[:600]))
        bad = [w for w in ("collection", "debt", "overdue", "past due") if any(w in x.lower() for x in replies)]
        out.append(("nothing about the debt before verification", not bad, ",".join(bad)))
    except Exception as e:
        out.append(("chat", False, str(e)[:300]))
    return out
