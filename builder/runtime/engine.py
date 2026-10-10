"""Call state machine that runs INSIDE the phone agent, in the `step` code node, after every customer turn
and after every bank call.

Contract with the workflow (built by builder/compile.py):
  in : V (the Freya `vars` dict). Customer input arrives in u_kind / u_text / u_date / u_amount / u_scope,
       extracted by the talk node that just ran. Bank results arrive as flattened keys
       '<api node>_response.data.<field>' (e.g. 'api_verify_response.data.verified').
  out: V['say'] (spoken verbatim by the next node), V['next'] (node key to route to),
       slot variables baked into the next bank call (q_field, q_answer, p_product, ...).
Everything brief-specific lives in S (the spec), injected by the compiler. The weak agent model never
decides anything here; it only classifies what the customer said.

Sandbox rules: imports limited to json/re/datetime; the source must never contain a double brace pair.
"""
import datetime
import json
import re

try:                                   # local tests import the sibling module; on Freya the compiler
    from builder.runtime import cal    # concatenates cal.py above this file, so these names exist already
    from builder.runtime.cal import *  # noqa: F401,F403
except Exception:
    pass

S = dict()   # injected spec


# ----------------------------------------------------------------------------------------------- helpers
CTX = dict()   # customer names, filled once per step from the call variables


def L(key, **kw):
    """Spec line with {placeholders} filled (customer names always available). Never raises."""
    t = S.get("lines", dict()).get(key, "")
    for k, v in list(kw.items()) + list(CTX.items()):
        t = t.replace("{" + k + "}", str(v))
    t = re.sub(r"\{[a-z_0-9]+\}", "", t)       # never speak an unfilled placeholder
    return re.sub(r"\s+", " ", t).strip()


def money(x):
    s = speak_amount(x)
    w = S.get("currency_word", "")
    return (s + " " + w).strip()


def say(V, *parts):
    pre = V.pop("_prefix", "") if "_prefix" in V else ""
    V["say"] = " ".join(p.strip() for p in (pre,) + parts if p and p.strip())


def jget(V, key, default=None):
    v = V.get(key)
    if v is None or v == "":
        return default
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return v
    return v


def st(V):
    return jget(V, "_state", None) or dict()


def put(V, state):
    V["_state"] = json.dumps(state)


def truthy(x):
    return str(x).strip().lower() in ("true", "1", "yes")


def resp(V, node, field):
    v = V.get(node + "_response.data." + field)
    if v is None:
        d = V.get(node + "_response.data")
        if isinstance(d, dict):
            v = d.get(field)
    return v


def num(x):
    try:
        if x is None or x == "":
            return None
        return float(x)
    except Exception:
        return None


def today_of(V):
    return parse_now(V.get("now")).date()


def ev(name):
    """Event -> dict(outcome, reason, queue, note)."""
    return S.get("events", dict()).get(name, dict())


# ----------------------------------------------------------------------------------------------- products
def read_products(V):
    out, i = [], 0
    while True:
        base = "api_account_response.data.products." + str(i) + "."
        pid = V.get(base + "product_id")
        if pid is None or pid == "":
            break
        p = dict()
        for k in list(V.keys()):
            if k.startswith(base):
                p[k[len(base):]] = V[k]
        out.append(p)
        i += 1
    if not out:
        raw = V.get("api_account_response.data.products")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = None
        if isinstance(raw, list):
            out = [x for x in raw if isinstance(x, dict)]
    return out


def band_for(days_late):
    for b in S["bands"]:
        lo, hi = b.get("min", -10 ** 9), b.get("max", 10 ** 9)
        if lo <= days_late <= hi:
            return b
    return S["bands"][-1]


def product_facts(V, raw):
    today = today_of(V)
    typ = str(raw.get("type", ""))
    names = S["products"]["names"]
    name = names.get(typ, typ.replace("_", " "))
    for k, v in raw.items():
        name = name.replace("{" + k + "}", str(v))
    full = num(raw.get(S["products"].get("amount_field", "past_due"))) or 0.0
    ff = S["products"]["floor_field"].get(typ)
    floor = num(raw.get(ff)) if ff else None
    if floor is None and S["products"].get("floor_pct") is not None:
        floor = round(full * float(S["products"]["floor_pct"]) / 100.0, 2)
    if floor is None:
        floor = full
    dl = int(num(raw.get(S["products"].get("days_field", "days_late"))) or 0)
    b = band_for(dl)
    deadline = cal_deadline(today, b["deadline"])
    return dict(id=str(raw.get("product_id")), type=typ, name=name, full=full, floor=floor, days_late=dl,
                band=b.get("name", ""), deadline=iso(deadline), attempts=int(b.get("attempts", 1)),
                used=0, too_much=False, floor_offered=False, vague_asked=False, offer=None,
                agreed=None, status="open", reason="", refused_offers=[], raw=raw)


def cal_deadline(today, rule):
    return deadline(today, rule)


# ----------------------------------------------------------------------------------------------- dates
def ladder_date(today, which, p):
    if which == "today":
        return today
    if which == "deadline":
        return datetime.date.fromisoformat(p["deadline"])
    if which == "last_business_day_this_week":
        d = last_business_day_of_week(today, 0)
        if d is None or d <= today:
            d = last_business_day_of_week(today, 1)
        return d
    if which == "last_business_day_next_week":
        return last_business_day_of_week(today, 1)
    if which.startswith("business_days_after:"):
        return add_business_days(today, int(which.split(":")[1]))
    return datetime.date.fromisoformat(p["deadline"])


def check_date(V, p, d):
    """-> (status, date). status: ok | past | after_deadline | not_business (date = proposal to offer)."""
    today = today_of(V)
    dl = datetime.date.fromisoformat(p["deadline"])
    if d < today:
        return "past", None
    if d > dl:
        return "after_deadline", dl
    if not is_business_day(d):
        nb = next_business_day(d)
        if nb > dl:
            return "after_deadline", dl
        return "not_business", nb
    return "ok", d


def check_amount(p, a):
    if a is None:
        return "none", None
    a = round(float(a), 2)
    if a > p["full"] + 0.005:
        return "ok", p["full"]
    if a + 0.005 < p["floor"]:
        return "below_floor", p["floor"]
    return "ok", a


def spoken(d):
    if isinstance(d, str):
        d = datetime.date.fromisoformat(d)
    return speak_date(d)


# ----------------------------------------------------------------------------------------------- input
def take_input(V, stage):
    """Extracted values of the talk node that just ran (variables are named per stage: <stage>_kind ...)."""
    g = lambda f: V.get(stage + "_" + f)
    k = str(g("kind") or "none").strip().lower()
    t = str(g("text") or "").strip()
    dt = str(g("date") or "").strip()
    a = num(g("amount"))
    sc = str(g("scope") or "none").strip().lower()
    side = str(g("side") or "none").strip().lower()
    if (stage + "_side") in V:
        V[stage + "_side"] = "none"
    if side != k and side in ("robot", "scam") and not (stage in ("open", "tp") and k == "unclear"):
        V["_prefix"] = L(side)
    elif side == "question" and k not in ("question", "purpose", "asks_why", "unclear", "none") and stage not in ("open", "tp", "id"):
        V["_prefix"] = L("no_info")
    V["_norm"] = str(g("norm") or "").strip()
    for f in ("text", "date", "norm"):
        if (stage + "_" + f) in V:
            V[stage + "_" + f] = ""
    if (stage + "_amount") in V:
        V[stage + "_amount"] = 0
    if (stage + "_kind") in V:
        V[stage + "_kind"] = "none"
    if (stage + "_scope") in V:
        V[stage + "_scope"] = "none"
    if a == 0:
        a = None
    return k, t, dt, a, sc


def go(V, node):
    V["next"] = node


def talk(V, stage, s):
    s["await"] = "talk"
    s["stage"] = stage
    put(V, s)
    go(V, "talk_open_again" if stage == "open" else "talk_" + stage)


def call(V, s, api, **slots):
    for k in list(V.keys()):            # stale results of an earlier call to the same node
        if k.startswith(api + "_response.data"):
            V[k] = ""
    for k, v in slots.items():
        V[k] = v
    s["await"] = api
    put(V, s)
    go(V, api)


# ----------------------------------------------------------------------------------------------- closing
def close(V, s, event, pre=""):
    e = ev(event)
    s["close_event"] = event
    V["c_outcome"] = e.get("outcome", "")
    V["c_reason"] = e.get("reason", "") or ""
    s["stage"] = "closing"
    say(V, pre, L("goodbye"))
    s["await"] = "api_close"
    put(V, s)
    go(V, "api_close")


def finish(V, s, pre=""):
    """End of a verified call: notes (if the brief uses them), then the outcome from the product states."""
    prods = s.get("products", [])
    if S.get("notes", dict()).get("enabled") and not s.get("transferred"):
        for p in prods:
            if p["status"] in ("refused", "hardship", "dispute", "paid", "service_error") and not p.get("noted"):
                p["noted"] = True
                s["pre"] = pre
                note_reason = ev(p["status"]).get("note") or p["status"]
                return call(V, s, "api_note", n_product=p["id"], n_reason=note_reason)
    pre = s.pop("pre", pre) if "pre" in s and not pre else pre
    if s.get("transferred"):
        return close(V, s, "transfer_" + s["transferred"], pre)
    if any(p["status"] == "recorded" for p in prods):
        return close(V, s, "promise", pre)
    reasons = [p["status"] for p in prods]
    if reasons and all(r == "paid" for r in reasons):
        return close(V, s, "paid", pre)
    for r in reasons:
        if r != "paid" and r in S.get("events", dict()):
            return close(V, s, r, pre)
    return close(V, s, "refused", pre)


# ----------------------------------------------------------------------------------------------- stages
def stage_init(V, s):
    s.update(stage="open", asks=1, questions=0, not_talk=0)
    say(V, L("opening"), L("confirm_ask", **names(V)))
    talk(V, "open", s)


def names(V):
    return dict(title=V.get("title", ""), first_name=V.get("first_name", ""), last_name=V.get("last_name", ""))


def common_intents(V, s, k, again, verified):
    """Robot / scam / human / no-talk handled the same in every stage. Returns True if handled."""
    if k == "robot":
        say(V, L("robot"), again)
        talk(V, s["stage"], s)
        return True
    if k == "scam":
        say(V, L("scam"), again)
        talk(V, s["stage"], s)
        return True
    if k == "human":
        if not s.get("human_asked") and S.get("human", dict()).get("ask_first", True):
            s["human_asked"] = True
            say(V, L("human_ask_help"))
            talk(V, s["stage"], s)
            return True
        s["transferred"] = "human"
        s["say_after_transfer"] = L("transfer")
        call(V, s, "api_transfer", t_queue=ev("transfer_human").get("queue", "general"))
        return True
    if k in ("not_talk", "refuse_talk"):
        s["not_talk"] = s.get("not_talk", 0) + 1
        if s["not_talk"] >= S.get("max_not_talk", 2):
            if verified:
                for p in s.get("products", []):
                    if p["status"] in ("open", "agreed"):
                        p["status"] = "refused"
                finish(V, s)
            else:
                close(V, s, "id_declined")
            return True
        say(V, L("not_talk_once"), again)
        talk(V, s["stage"], s)
        return True
    return False


def stage_open(V, s, k, t):
    again = L("confirm_ask", **names(V))
    if k == "confirmed":
        return start_identity(V, s)
    if k == "third_party":
        s["stage"] = "tp"
        s["tp_tries"] = 0
        say(V, L("tp_ask"))
        return talk(V, "tp", s)
    if k == "wrong_number":
        return close(V, s, "wrong_number", L("wrong_number"))
    if k == "deceased":
        return close(V, s, "deceased", L("condolence"))
    if k in ("robot", "scam", "purpose", "question"):
        s["asks"] = s.get("asks", 1) + 1
        line = dict(robot=L("robot"), scam=L("scam"), purpose=L("purpose_before_verify")).get(k, L("no_info"))
        if s["asks"] > S["confirm"]["max_asks"] + 1:
            return close(V, s, "unclear")
        say(V, line, again)
        return talk(V, "open", s)
    if common_intents(V, s, k, again, False):
        return
    # unclear / hello / anything else
    if s.get("asks", 1) >= S["confirm"]["max_asks"]:
        return close(V, s, "unclear")
    s["asks"] = s.get("asks", 1) + 1
    say(V, again)
    return talk(V, "open", s)


def stage_tp(V, s, k, t, dtxt):
    today = today_of(V)
    if k == "wrong_number":
        return close(V, s, "wrong_number", L("wrong_number"))
    if k == "deceased":
        return close(V, s, "deceased", L("condolence"))
    if k == "customer_now":   # the customer came to the phone
        s["asks"] = 1
        say(V, L("confirm_ask", **names(V)))
        return talk(V, "open", s)
    if k in ("purpose", "offers_pay", "question", "robot", "scam"):
        line = L("robot") if k == "robot" else (L("scam") if k == "scam" else L("tp_no_info"))
        say(V, line, L("tp_ask"))
        return talk(V, "tp", s)
    if k in ("gives_time", "unclear", "none") and (dtxt or t):
        d, hm = parse_callback(dtxt + " " + t, today, V)
        ok = d is not None and hm is not None and callback_ok(V, d, hm)
        if ok:
            s["cb"] = [iso(d), hm]
            s["pre"] = L("tp_booked", date=spoken(d), time=hm)
            return call(V, s, "api_callback", cb_date=iso(d), cb_time=hm)
        s["tp_tries"] = s.get("tp_tries", 0) + 1
        if s["tp_tries"] >= S["callback"].get("max_asks", 2):
            return close(V, s, "no_callback")
        if d is not None and hm is None:
            say(V, L("tp_ask_time"))
        else:
            say(V, L("tp_outside_window"))
        return talk(V, "tp", s)
    if k in ("no_time", "declines"):
        return close(V, s, "no_callback")
    say(V, L("tp_ask"))
    return talk(V, "tp", s)


def parse_callback(text, today, V):
    t = text.lower()
    d = parse_spoken_date(t, today, S.get("date_rules"))
    if d is None and re.search(r"\b(this )?(morning|afternoon|evening|later|tonight)\b", t):
        d = today
    hm = None
    m = re.search(r"\b(\d{1,2})(?::|\.)(\d{2})\s*(am|pm|a\.m\.|p\.m\.)?", t)
    if m:
        h, mi, ap = int(m.group(1)), int(m.group(2)), (m.group(3) or "")
    else:
        m = re.search(r"\b(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.|o'clock|oclock)", t)
        if m:
            h, mi, ap = int(m.group(1)), 0, m.group(2)
        else:
            m = re.search(r"\b(?:at|around|about)\s+([a-z]+)(?:\s+(thirty|fifteen|forty five))?", t)
            if m and m.group(1) in NUM_WORDS:
                h = NUM_WORDS[m.group(1)]
                mi = dict(thirty=30, fifteen=15).get(m.group(2) or "", 0)
                ap = ""
            else:
                return d, None
    if ap.startswith("p") and h < 12:
        h += 12
    if not ap and h < 8 and ("afternoon" in t or "evening" in t or h <= 7):
        h += 12
    if "noon" in t and not m:
        h, mi = 12, 0
    if h > 23 or mi > 59:
        return d, None
    return d, "%02d:%02d" % (h, mi)


def callback_ok(V, d, hm):
    c = S["callback"]
    now = parse_now(V.get("now"))
    today = now.date()
    allowed = []
    for k in c.get("days", ["today", "next_business_day"]):
        if k == "today":
            allowed.append(today)
        elif k == "next_business_day":
            allowed.append(next_business_day(today, include_self=False))
        elif k == "tomorrow":
            allowed.append(today + datetime.timedelta(days=1))
        elif k.startswith("within_business_days:"):
            n = int(k.split(":")[1])
            x = today
            for _ in range(n):
                x = next_business_day(x, include_self=False)
                allowed.append(x)
    if d not in allowed:
        return False
    if c.get("business_days_only") and not is_business_day(d):
        return False
    if not (c.get("start", "00:00") <= hm <= c.get("end", "23:59")):
        return False
    if c.get("after_now", True) and d == today and hm <= now.strftime("%H:%M"):
        return False
    return True


def start_identity(V, s):
    s.update(stage="id", qi=0, wrong=0, declined=0, partial="", id_explained=False)
    q = S["identity"]["questions"][0]
    say(V, L("id_intro"), q["ask"])
    return talk(V, "id", s)


def stage_id(V, s, k, t):
    qs = S["identity"]["questions"]
    q = qs[s["qi"]]
    if k == "asks_why" and not s.get("why_answered"):
        s["why_answered"] = True          # explaining why the questions are needed is not a refusal
        say(V, L("id_why"), q["ask"])
        return talk(V, "id", s)
    purpose_declines = S["identity"].get("purpose_is_decline", S["identity"].get("why_is_decline", True))
    if k in ("refuses", "asks_why") or (k == "purpose" and purpose_declines) or (k == "question" and S["identity"].get("question_is_decline")):
        s["declined"] = s.get("declined", 0) + 1
        if s["declined"] >= 2:
            return close(V, s, "id_declined", L("id_declined"))
        say(V, L("id_explain"), q["ask"])
        return talk(V, "id", s)
    if k in ("robot", "scam", "human", "not_talk"):
        if common_intents(V, s, k, q["ask"], False):
            return
    if k == "wrong_person":
        return close(V, s, "wrong_number", L("wrong_number"))
    combined = (s.get("partial", "") + " " + t).strip()
    ans = normalize_answer(q, combined if q.get("kind") in ("digits", "date", "year") else t)
    if not ans and q.get("kind") in ("date", "year") and t and not s.get("partial"):
        ans = "partial"            # e.g. "the fourteenth of March..." with the year still to come
    if ans == "partial":
        s["partial"] = (s.get("partial", "") + " " + t).strip()
        say(V, L("id_continue"))
        return talk(V, "id", s)
    s["partial"] = ""
    if not ans:
        ans = norm_fallback(q, V.get("_norm", ""))
    if not ans:
        s["repeats"] = s.get("repeats", 0) + 1
        say(V, L("id_repeat"), q["ask"] if s["repeats"] < 2 else (L("id_format_hint") or q["ask"]))
        return talk(V, "id", s)
    s["repeats"] = 0
    s["last_answer"] = ans
    return call(V, s, "api_verify", q_field=q["field"], q_answer=ans)


def norm_fallback(q, norm):
    """The extractor's own normalisation, used only when our parser found nothing."""
    norm = str(norm or "").strip()
    if not norm:
        return ""
    kind = q.get("kind", "text")
    if kind == "date":
        return norm if re.fullmatch(r"(19|20)\d\d-\d\d-\d\d", norm) else ""
    if kind == "digits":
        d = re.sub(r"\D", "", norm)
        n = int(q.get("length") or 0)
        return d if d and (not n or len(d) == n) else ""
    if kind == "year":
        return norm if re.fullmatch(r"(19|20)\d\d", norm) else ""
    if kind == "upper":
        return re.sub(r"[^A-Za-z0-9]", "", norm).upper()
    return norm


def normalize_answer(q, text):
    kind = q.get("kind", "text")
    if not text:
        return ""
    if kind == "date":
        return parse_birth_date(text, S["identity"].get("date_order", "dmy"))
    if kind == "digits":
        d = digits_only(text)
        n = int(q.get("length") or 0)
        if n and 0 < len(d) < n:
            return "partial"
        if n and len(d) > n:
            d = d[-n:]
        return d
    if kind == "year":
        m = re.search(r"\b(19\d\d|20\d\d)\b", text)
        if m:
            return m.group(1)
        n = words_to_number(text)
        if n and 1900 <= n <= 2100:
            return str(int(n))
        b = parse_birth_date("1 january " + text)
        return b[:4] if b else ""
    if kind == "upper":
        return re.sub(r"[^A-Za-z0-9]", "", text).upper()
    return text.strip()


def after_verify(V, s):
    node = "api_verify"
    qs = S["identity"]["questions"]
    R = S["identity"].get("response", dict())
    ok = resp(V, node, R.get("ok", "ok"))
    verified = resp(V, node, R.get("verified", "verified"))
    allv = resp(V, node, R.get("all_verified", "all_verified"))
    left = resp(V, node, R.get("left", "wrong_answers_left"))
    hint = resp(V, node, R.get("hint", "hint"))
    V["api_verify_response.data.hint"] = ""
    q = qs[s["qi"]]
    if ok is not None and not truthy(ok) and not truthy(verified):
        err = str(resp(V, node, "error") or "").lower()
        if "locked" in err or "ended" in err or "too many" in err:
            return close(V, s, "id_failed", L("id_failed"))
        say(V, L("id_repeat"), q["ask"])
        return talk(V, "id", s)
    if truthy(allv) or (truthy(verified) and s["qi"] + 1 >= len(qs)):
        return call(V, s, "api_account")
    if truthy(verified):
        s["qi"] += 1
        say(V, qs[s["qi"]]["ask"])
        return talk(V, "id", s)
    if hint and str(hint) in S["identity"].get("hints", dict()):
        say(V, S["identity"]["hints"][str(hint)])
        return talk(V, "id", s)
    s["wrong"] = s.get("wrong", 0) + 1
    lv = num(left)
    if (lv is not None and lv <= 0) or s["wrong"] >= S["identity"].get("max_wrong", 3):
        return close(V, s, "id_failed", L("id_failed"))
    say(V, L("id_wrong"), q["ask"])
    return talk(V, "id", s)


def after_account(V, s):
    raws = read_products(V)
    if not raws:
        n = s.get("acct_tries", 0) + 1
        s["acct_tries"] = n
        if n < 2:
            return call(V, s, "api_account")
        return close(V, s, "service_error", L("no_info"))
    prods = [product_facts(V, r) for r in raws]
    s["products"] = prods
    s["ci"] = -1
    s["stage"] = "nego"
    lines = [L("disclose_intro")]
    for p in prods:
        lines.append(L("product_line", name=p["name"], amount=money(p["full"]), days=p["days_late"]))
    if len(prods) > 1:
        lines.append(L("ask_today_multi"))
    else:
        lines.append(L("ask_today"))
    s["phase"] = "today"
    say(V, *lines)
    return talk(V, "nego", s)


def cur(s):
    ci = s.get("ci", -1)
    if 0 <= ci < len(s["products"]):
        return s["products"][ci]
    return None


def next_open(s):
    for i, p in enumerate(s["products"]):
        if p["status"] == "open":
            return i
    return None


def make_offer(V, s, p, step_idx, pre=""):
    """Persuasion attempt number step_idx (1-based)."""
    today = today_of(V)
    ladder = S["ladder"]
    st_ = ladder[min(step_idx, len(ladder)) - 1]
    amt = p["full"]
    if st_.get("amount") == "floor" or (st_.get("amount") == "full_or_floor" and p["too_much"]):
        amt = p["floor"]
    elif str(st_.get("amount", "")).startswith("pct:"):
        amt = max(p["floor"], round(p["full"] * float(st_["amount"][4:]) / 100.0, 2))
    d = ladder_date(today, st_.get("date", "deadline"), p)
    dl = datetime.date.fromisoformat(p["deadline"])
    if d > dl:
        d = dl
    offer = [round(amt, 2), iso(d)]
    if offer in p["refused_offers"] and step_idx < p["attempts"]:
        return make_offer(V, s, p, step_idx + 1, pre)
    p["used"] = step_idx
    p["offer"] = offer
    line = L("offer_floor_date" if amt == p["floor"] and amt < p["full"] else "offer",
             name=p["name"], amount=money(amt), date=spoken(d))
    say(V, pre, line)
    return talk(V, "nego", s)


def refusal(V, s, p, pre=""):
    """A flat refusal / non-answer on product p: consume one persuasion attempt or give up."""
    if p.get("offer"):
        p["refused_offers"].append(p["offer"])
    if p["used"] < p["attempts"]:
        return make_offer(V, s, p, p["used"] + 1, pre)
    p["status"] = "refused"
    p["offer"] = None
    return advance(V, s, pre)


def advance(V, s, pre=""):
    """Move to the next open product, or to the read-back, or finish."""
    i = next_open(s)
    if i is not None:
        s["ci"] = i
        p = s["products"][i]
        intro = L("next_product", name=p["name"], amount=money(p["full"])) if len(s["products"]) > 1 else ""
        return make_offer(V, s, p, 1, (pre + " " + intro).strip())
    agreed = [p for p in s["products"] if p["status"] == "agreed"]
    if agreed:
        return readback(V, s, pre)
    return finish(V, s, pre)


def readback(V, s, pre=""):
    agreed = [p for p in s["products"] if p["status"] == "agreed"]
    parts = []
    for p in agreed:
        extra = L("clamped_note", date=spoken(p["agreed"][1])) if p.get("clamped") else ""
        parts.append((L("readback_item", name=p["name"], amount=money(p["agreed"][0]), date=spoken(p["agreed"][1])) + " " + extra).strip())
    s["stage"] = "confirm"
    say(V, pre, L("readback_intro"), " ".join(parts), L("confirm_q"))
    return talk(V, "confirm", s)


def agree(p, amount, date, clamped=False):
    p["agreed"] = [round(float(amount), 2), date]
    p["status"] = "agreed"
    p["offer"] = None
    p["clamped"] = clamped


def apply_proposal(V, s, p, dtxt, a, scope_all=False):
    """Customer proposed a date and/or an amount for p. Returns (handled, pre_line)."""
    today = today_of(V)
    amount = None
    if a is not None:
        stt, val = check_amount(p, a)
        if stt == "below_floor":
            if p["floor_offered"]:
                return "refuse", ""
            p["floor_offered"] = True
            p["too_much"] = True
            d0 = p["offer"][1] if p.get("offer") else None
            p["offer"] = [p["floor"], d0]
            return "ask", L("below_floor", amount=money(p["floor"]), name=p["name"])
        amount = val
    date = None
    if dtxt:
        d = parse_spoken_date(dtxt, today, S.get("date_rules"))
        if d is None:
            vague = True
        else:
            vague = False
            stt, val = check_date(V, p, d)
            if stt == "ok":
                date = iso(val)
            elif stt == "past":
                return "ask", L("date_past")
            elif stt == "not_business":
                p["offer"] = [amount if amount is not None else default_amount(p), iso(val)]
                return "ask", L("not_business_day", date=spoken(val))
            elif stt == "after_deadline":
                if scope_all and S.get("multi", dict()).get("clamp_single_date", True) and len(s["products"]) > 1:
                    date = iso(val)
                    p["clamped"] = True
                else:
                    p["after_deadline_offered"] = True
                    p["offer"] = [amount if amount is not None else default_amount(p), iso(val)]
                    return "ask", L("after_deadline", date=spoken(val))
        if vague:
            if not p["vague_asked"]:
                p["vague_asked"] = True
                return "ask", L("vague_ask")
            dl = datetime.date.fromisoformat(p["deadline"])
            p["offer"] = [amount if amount is not None else default_amount(p), iso(dl)]
            return "ask", L("propose_deadline", date=spoken(dl), amount=money(p["offer"][0]))
    if amount is not None and date is not None:
        agree(p, amount, date, p.get("clamped", False))
        return "agreed", ""
    if date is not None:
        agree(p, p["offer"][0] if p.get("offer") and p["offer"][0] else default_amount(p), date, p.get("clamped", False))
        return "agreed", ""
    if amount is not None:
        if p.get("offer") and p["offer"][1]:
            agree(p, amount, p["offer"][1])
            return "agreed", ""
        p["offer"] = [amount, None]
        return "ask", L("ask_date_for_amount", amount=money(amount))
    return "none", ""


def default_amount(p):
    return p["floor"] if p["too_much"] and p["floor_offered"] else p["full"]


def special(V, s, k, p):
    """Paid / dispute / hardship / restructure on product p (or the call). Returns True if handled."""
    multi = len(s["products"]) > 1
    if k == "already_paid":
        if multi and S.get("multi", dict()).get("continue_after_paid", True):
            p["status"] = "paid"
            return advance(V, s, L("paid_line")) or True
        p["status"] = "paid"
        for q in s["products"]:
            if q["status"] == "open":
                q["status"] = "paid"
        finish(V, s, L("paid_line"))
        return True
    if k == "dispute":
        p["status"] = "dispute"
        if multi and S.get("multi", dict()).get("continue_after_dispute", True):
            advance(V, s, L("dispute_line"))
            return True
        for q in s["products"]:
            if q["status"] == "open":
                q["status"] = "dispute"
        finish(V, s, L("dispute_line"))
        return True
    if k == "hardship":
        s["stage"] = "hardship"
        s["hardship_offered"] = True
        say(V, L("hardship"))
        talk(V, "hardship", s)
        return True
    if k == "restructure":
        s["transferred"] = "restructuring"
        for q in s["products"]:
            if q["status"] == "agreed":
                q["status"] = "open"
        s["say_after_transfer"] = L("restructure_line")
        call(V, s, "api_transfer", t_queue=ev("transfer_restructuring").get("queue", "restructuring"))
        return True
    return False


def stage_nego(V, s, k, t, dtxt, a, scope):
    prods = s["products"]
    multi = len(prods) > 1
    if s.get("phase") == "today":
        s["phase"] = "items"
        if k in ("yes", "agrees", "pay_today"):
            for p in prods:
                agree(p, p["full"], iso(today_of(V)))
            return readback(V, s)
        if k in ("proposes", "gives_date", "gives_amount", "too_much", "vague") or dtxt or a is not None:
            s["ci"] = next_open(s)
            if multi and (scope == "all" or (dtxt and a is None and scope != "one")):
                return propose_all(V, s, dtxt, a, k)
        elif k in ("no", "refuses", "cannot", "none", "unclear"):
            s["ci"] = next_open(s)
            p = cur(s)
            intro = L("next_product", name=p["name"], amount=money(p["full"])) if multi else ""
            return make_offer(V, s, p, 1, intro)
        else:
            s["ci"] = next_open(s)
    p = cur(s)
    if p is None:
        s["ci"] = next_open(s)
        p = cur(s)
        if p is None:
            return advance(V, s)
    again = L("repeat_offer", name=p["name"], amount=money(p["offer"][0]), date=spoken(p["offer"][1])) if p.get("offer") and p["offer"][1] else L("ask_today")
    if special(V, s, k, p):
        return
    if common_intents(V, s, k, again, True):
        return
    if k in ("question", "purpose"):
        say(V, L("no_info"), again)
        return talk(V, "nego", s)
    if multi and scope == "all" and (dtxt or a is not None or k in ("yes", "agrees")):
        return propose_all(V, s, dtxt, a, k)
    if k == "too_much":
        if p["floor_offered"]:
            return refusal(V, s, p)
        p["too_much"] = True
        p["floor_offered"] = True
        d0 = p["offer"][1] if p.get("offer") else None
        p["offer"] = [p["floor"], d0]
        line = L("offer_floor", amount=money(p["floor"]), name=p["name"])
        if dtxt or a is not None:
            res, pre = apply_proposal(V, s, p, dtxt, None)
            if res == "agreed":
                p["agreed"][0] = p["floor"]
                return advance(V, s)
        say(V, line)
        return talk(V, "nego", s)
    if dtxt or a is not None or k in ("proposes", "gives_date", "gives_amount", "vague"):
        res, pre = apply_proposal(V, s, p, dtxt if dtxt else (t if k == "vague" else ""), a)
        if res == "agreed":
            return advance(V, s)
        if res == "ask":
            say(V, pre)
            return talk(V, "nego", s)
        if res == "refuse":
            return refusal(V, s, p, L("below_floor_again"))
    if k in ("yes", "agrees", "pay_today"):
        if p.get("offer") and p["offer"][1]:
            agree(p, p["offer"][0], p["offer"][1])
            return advance(V, s)
        if p.get("offer") and not p["offer"][1]:
            agree(p, p["offer"][0], iso(today_of(V)))
            return advance(V, s)
        agree(p, default_amount(p), iso(today_of(V)))
        return advance(V, s)
    if k in ("no", "refuses", "cannot", "none", "unclear"):
        if p.get("after_deadline_offered") and S.get("rules", dict()).get("refuse_deadline_is_refusal", True):
            p["after_deadline_offered"] = False
        return refusal(V, s, p)
    say(V, again)
    return talk(V, "nego", s)


def propose_all(V, s, dtxt, a, k):
    """One date (and maybe amount) for every open product."""
    pre_lines = []
    for p in s["products"]:
        if p["status"] != "open":
            continue
        if k in ("yes", "agrees") and not dtxt and a is None and p.get("offer"):
            agree(p, p["offer"][0], p["offer"][1])
            continue
        res, pre = apply_proposal(V, s, p, dtxt, a if len(s["products"]) == 1 else None, scope_all=True)
        if res != "agreed":
            s["ci"] = s["products"].index(p)
            say(V, pre)
            return talk(V, "nego", s)
    return advance(V, s)


def stage_hardship(V, s, k, t, dtxt, a):
    p = cur(s) or (s["products"][0] if s["products"] else None)
    if k in ("yes", "agrees"):
        s["transferred"] = "support"
        s["say_after_transfer"] = L("transfer")
        V["say"] = L("transfer")
        return call(V, s, "api_transfer", t_queue=ev("transfer_support").get("queue", "support"))
    if (dtxt or a is not None) and p is not None:
        s["stage"] = "nego"
        res, pre = apply_proposal(V, s, p, dtxt, a)
        if res == "agreed":
            return advance(V, s)
        say(V, pre)
        return talk(V, "nego", s)
    for q in s["products"]:
        if q["status"] in ("open",):
            q["status"] = "hardship"
    return finish(V, s, L("hardship_declined"))


def stage_confirm(V, s, k, t, dtxt, a, scope):
    agreed = [p for p in s["products"] if p["status"] == "agreed"]
    if k in ("yes", "agrees", "confirm"):
        s["rec_queue"] = [p["id"] for p in agreed]
        return record_next(V, s)
    if dtxt or a is not None:
        target = agreed[0] if len(agreed) == 1 else None
        if target is None:
            for p in agreed:
                p["status"] = "open"
            return propose_all(V, s, dtxt, a, "proposes")
        target["status"] = "open"
        target["offer"] = [target["agreed"][0], target["agreed"][1]]
        res, pre = apply_proposal(V, s, target, dtxt, a)
        if res == "agreed":
            return readback(V, s)
        s["stage"] = "nego"
        s["ci"] = s["products"].index(target)
        say(V, pre)
        return talk(V, "nego", s)
    if special(V, s, k, agreed[0] if agreed else s["products"][0]):
        return
    if common_intents(V, s, k, L("confirm_q"), True):
        return
    if k in ("no", "refuses"):
        for p in agreed:
            p["status"] = "open"
            p["refused_offers"].append(list(p["agreed"]))
        s["stage"] = "nego"
        s["ci"] = next_open(s)
        return refusal(V, s, cur(s))
    say(V, L("confirm_q"))
    return talk(V, "confirm", s)


def record_next(V, s):
    q = s.get("rec_queue", [])
    if not q:
        rec = [p for p in s["products"] if p["status"] == "recorded"]
        failed = [p for p in s["products"] if p["status"] == "service_error"]
        lines = []
        if rec:
            lines.append(L("recorded"))
            lines.append(L("sms_line"))
        if failed:
            lines.append(L("record_failed"))
        return finish(V, s, " ".join(lines))
    pid = q[0]
    p = [x for x in s["products"] if x["id"] == pid][0]
    s["rec_try"] = s.get("rec_try", 0)
    return call(V, s, "api_promise", p_product=p["id"], p_amount=p["agreed"][0], p_date=p["agreed"][1])


def after_promise(V, s):
    q = s.get("rec_queue", [])
    pid = q[0]
    p = [x for x in s["products"] if x["id"] == pid][0]
    ok = resp(V, "api_promise", "ok")
    V["api_promise_response.data.ok"] = ""
    if truthy(ok):
        p["status"] = "recorded"
        q.pop(0)
        s["rec_try"] = 0
        return record_next(V, s)
    s["rec_try"] = s.get("rec_try", 0) + 1
    if s["rec_try"] < 2:
        return call(V, s, "api_promise", p_product=p["id"], p_amount=p["agreed"][0], p_date=p["agreed"][1])
    p["status"] = "service_error"
    q.pop(0)
    s["rec_try"] = 0
    return record_next(V, s)


# ----------------------------------------------------------------------------------------------- entry
def run(V):
    s = st(V)
    aw = s.get("await", "")
    if not s:   # the initial talk_open node already spoke the opening and the first identity ask
        s = dict(stage="open", asks=1, questions=0, not_talk=0)
    if aw == "api_verify":
        return after_verify(V, s)
    if aw == "api_account":
        return after_account(V, s)
    if aw == "api_promise":
        return after_promise(V, s)
    if aw == "api_note":
        return finish(V, s)
    if aw == "api_callback":
        return close(V, s, "callback", s.pop("pre", ""))
    if aw == "api_transfer":
        return close(V, s, "transfer_" + s.get("transferred", "human"), s.get("say_after_transfer", ""))
    if aw == "api_close":
        go(V, "end")
        return
    stage = s.get("stage", "open")
    k, t, dtxt, a, scope = take_input(V, stage)
    if stage == "open":
        return stage_open(V, s, k, t)
    if stage == "tp":
        return stage_tp(V, s, k, t, dtxt)
    if stage == "id":
        return stage_id(V, s, k, t)
    if stage == "nego":
        return stage_nego(V, s, k, t, dtxt, a, scope)
    if stage == "hardship":
        return stage_hardship(V, s, k, t, dtxt, a)
    if stage == "confirm":
        return stage_confirm(V, s, k, t, dtxt, a, scope)
    go(V, "end")


def main(V):
    CTX.update(names(V))
    try:
        run(V)
    except Exception as e:  # never let the call die: apologise and close safely
        V["engine_error"] = (type(e).__name__ + ": " + str(e))[:300]
        s = st(V)
        if s.get("stage") == "closing":
            go(V, "end")
            return
        if s.get("products"):
            try:
                return finish(V, s, L("no_info"))
            except Exception:
                pass
        V["c_outcome"] = S.get("events", dict()).get("refused", dict()).get("outcome", "")
        V["c_reason"] = S.get("events", dict()).get("refused", dict()).get("reason", "")
        say(V, L("goodbye"))
        V["_state"] = json.dumps(dict(stage="closing"))
        go(V, "api_close")
