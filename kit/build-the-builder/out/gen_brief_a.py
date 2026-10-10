"""Generate out/brief-a.workflow.json from Brief A and tools/openapi.json."""
import json, pathlib

BASE = "https://freya-bank-mock.freyavoice.workers.dev/v1"
OUT = pathlib.Path(__file__).resolve().parent / "brief-a.workflow.json"

HDR = {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}}

POST_COMMON = """try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if not isinstance(d, dict):
            d = dict(ok=False, error='service unavailable')
            result['data'] = d
        ok = str(d.get('ok')).lower() == 'true'
        d['ok'] = ok
        d['what_to_do_next'] = (OKMSG) if ok else (FAILMSG)
except Exception:
    pass
"""


def post_simple(okmsg, failmsg):
    return POST_COMMON.replace("OKMSG", repr(okmsg)).replace("FAILMSG", repr(failmsg))


def api_tool(name, path, body, required, desc="", mapping=None, pre="", post="", retries=0):
    t = {
        "type": "function",
        "config": {"timeoutMs": 12000, "maxRetries": retries},
        "function": {
            "name": name,
            "handler": "__function__:api_call",
            "description": desc or name,
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "default": BASE + path},
                    "method": {"type": "string", "default": "POST"},
                    "headers": HDR,
                    "body": {"type": "object", "properties": body, "required": required},
                },
            },
        },
    }
    if mapping:
        t["response_mapping"] = mapping
    if pre:
        t["pre_process_code"] = pre
    if post:
        t["post_process_code"] = post
    return t


CID = {"type": "string", "default": "{{customer_id}}"}


def cond_true(var):
    return [{"variable": var, "operator": "equals", "operand": "true"},
            {"variable": var, "operator": "equals", "operand": "True"}]


def any_of(conds):
    return {"logic": "or", "conditions": conds}


def go(target, desc, conds):
    return {"target_node": target, "description": desc, "condition": any_of(conds)}


def tool_go(target, desc):
    return {"target_node": target, "description": desc, "is_tool_call": True,
            "condition": {"operator": "matches_intent", "description": desc}}


def always(target):
    return {"target_node": target, "description": "always", "condition": {"operator": "always"}}


# ---------------------------------------------------------------- code: all date and account facts
FACTS_CODE = r'''import datetime, json, re
HOL = set(['2026-10-26', '2026-11-11', '2026-11-26', '2026-12-25', '2027-01-01'])
WD = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
MN = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
def fmt(d):
    return WD[d.weekday()] + ' ' + str(d.day) + ' ' + MN[d.month - 1] + ' ' + str(d.year)
def isbd(d):
    return d.weekday() < 5 and d.isoformat() not in HOL
def add_bd(d, n):
    x = d
    c = 0
    while c < n:
        x = x + datetime.timedelta(days=1)
        if isbd(x):
            c += 1
    return x
def money(v):
    return '{:,.2f}'.format(float(v))
try:
    raw = str(vars.get('now') or '').strip().replace(' ', 'T')
    try:
        now = datetime.datetime.fromisoformat(raw[:16])
    except Exception:
        now = datetime.datetime.fromisoformat(raw[:10] + 'T09:00')
except Exception:
    now = datetime.datetime.now()
today = now.date()
vars['today_iso'] = today.isoformat()
vars['today_text'] = fmt(today) + ' (' + today.isoformat() + '), time ' + now.strftime('%H:%M')
# ---- callback window: today or next business day, 10:00 to 19:00, later than now
nbd = add_bd(today, 1)
cb = []
earliest = now + datetime.timedelta(minutes=1)
if earliest.time() <= datetime.time(19, 0):
    start = max(datetime.time(10, 0), earliest.time().replace(second=0, microsecond=0))
    cb.append('today, ' + fmt(today) + ' (' + today.isoformat() + '), from ' + start.strftime('%H:%M') + ' to 19:00')
cb.append('the next business day, ' + fmt(nbd) + ' (' + nbd.isoformat() + '), from 10:00 to 19:00')
tomorrow = today + datetime.timedelta(days=1)
extra = ''
if tomorrow != nbd:
    extra = ' Tomorrow, ' + fmt(tomorrow) + ', is NOT a business day, so it is outside the window.'
vars['callback_facts'] = 'Allowed callback times (both ends included): ' + ' ; or '.join(cb) + '. Any other day or time is outside the window.' + extra
# ---- account
prod = None
try:
    p = vars.get('products')
    if isinstance(p, str):
        p = json.loads(p)
    if isinstance(p, list) and len(p) > 0 and isinstance(p[0], dict):
        prod = p[0]
except Exception:
    prod = None
if prod is None:
    flat = dict()
    for k in list(vars.keys()):
        m = re.search(r'products(?:\.0|\[0\])\.(\w+)$', str(k))
        if m:
            flat[m.group(1)] = vars.get(k)
    for f in ['product_id', 'type', 'card_last4', 'past_due', 'days_late', 'minimum_payment', 'instalment_amount']:
        v = vars.get('acc_' + f)
        if v is not None and str(v) != '' and f not in flat:
            flat[f] = v
    if flat.get('type') and flat.get('past_due') is not None:
        prod = flat
known = False
try:
    if prod is not None:
        ptype = str(prod.get('type'))
        past_due = float(prod.get('past_due'))
        days_late = int(float(prod.get('days_late')))
        last4 = str(prod.get('card_last4') or '').replace('.0', '')
        if ptype == 'credit_card':
            phrase = 'credit card ending ' + last4
            floor = float(prod.get('minimum_payment'))
            floor_label = 'minimum payment'
        else:
            phrase = 'personal loan' if ptype == 'personal_loan' else 'car loan'
            floor = float(prod.get('instalment_amount'))
            floor_label = 'instalment amount'
        if days_late <= 7:
            band = 'early'
            deadline = add_bd(today, 12)
            attempts = 1
        else:
            band = 'late'
            deadline = add_bd(today, 7)
            attempts = 2
        # attempt 1: last business day of this week, or of next week when today is that day
        monday = today - datetime.timedelta(days=today.weekday())
        def last_bd_of_week(mon):
            x = mon + datetime.timedelta(days=4)
            while x >= mon and not isbd(x):
                x = x - datetime.timedelta(days=1)
            return x
        a1 = last_bd_of_week(monday)
        if a1 <= today:
            a1 = last_bd_of_week(monday + datetime.timedelta(days=7))
        if a1 > deadline:
            a1 = deadline
        vars['acc_product_id'] = str(prod.get('product_id') or 'p1')
        vars['product_phrase'] = phrase
        vars['past_due_text'] = money(past_due)
        vars['floor_text'] = money(floor)
        vars['days_late_text'] = str(days_late)
        vars['deadline_text'] = fmt(deadline) + ' (' + deadline.isoformat() + ')'
        vars['attempt1_text'] = fmt(a1) + ' (' + a1.isoformat() + ')'
        lines = []
        lines.append('Product: ' + phrase + ' (product_id ' + vars['acc_product_id'] + ').')
        lines.append('FULL past-due amount: ' + money(past_due) + '.')
        lines.append('FLOOR (' + floor_label + '): ' + money(floor) + '. An amount from ' + money(floor) + ' up to ' + money(past_due) + ' (both included) can be accepted. Below ' + money(floor) + ' cannot be recorded. Above ' + money(past_due) + ' cannot be recorded.')
        lines.append('Days late: ' + str(days_late) + ', so the band is ' + band + '.')
        lines.append('TODAY: ' + fmt(today) + ' (' + today.isoformat() + ')' + (' - a business day.' if isbd(today) else ' - NOT a business day, so today cannot be a promise date.'))
        lines.append('DEADLINE (latest date a promise can have): ' + fmt(deadline) + ' (' + deadline.isoformat() + ').')
        lines.append('Persuasion attempts allowed: ' + str(attempts) + '.')
        lines.append('Attempt 1 offer: the full amount ' + money(past_due) + ' (or the floor ' + money(floor) + ' if the customer already said the full amount is too much) on ' + fmt(a1) + ' (' + a1.isoformat() + ').')
        if attempts >= 2:
            lines.append('Attempt 2 offer: the floor ' + money(floor) + ' on the deadline ' + fmt(deadline) + ' (' + deadline.isoformat() + ').')
        else:
            lines.append('There is NO attempt 2 for this customer.')
        lines.append('')
        lines.append('CALENDAR (only dates marked ALLOWED can be promise dates):')
        d = today
        end = deadline + datetime.timedelta(days=10)
        while d <= end:
            tag = ''
            if d > deadline:
                tag = 'NOT allowed, after the deadline'
            elif d.isoformat() in HOL:
                tag = 'NOT allowed, bank holiday; offer ' + fmt(add_bd(d, 1)) + ' instead' + (' (that is after the deadline, so offer the deadline)' if add_bd(d, 1) > deadline else '')
            elif d.weekday() >= 5:
                tag = 'NOT allowed, weekend; offer ' + fmt(add_bd(d, 1)) + ' instead' + (' (that is after the deadline, so offer the deadline)' if add_bd(d, 1) > deadline else '')
            else:
                tag = 'ALLOWED'
            lines.append('  ' + d.isoformat() + ' ' + fmt(d) + (' (today)' if d == today else '') + ': ' + tag)
            d = d + datetime.timedelta(days=1)
        lines.append('')
        lines.append('WEEKDAY WORDS ("this X" = the X of the current Monday-to-Sunday week; "next X" = the X of the following week):')
        for i in range(7):
            t1 = monday + datetime.timedelta(days=i)
            t2 = t1 + datetime.timedelta(days=7)
            lines.append('  this ' + WD[i] + ' = ' + t1.isoformat() + (' (already past)' if t1 < today else '') + ' ; next ' + WD[i] + ' = ' + t2.isoformat())
        vars['deal_facts'] = '\n'.join(lines)
        known = True
except Exception:
    known = False
if not known:
    vars['deal_facts'] = 'The account details are not available.'
    for k in ['product_phrase', 'past_due_text', 'floor_text', 'days_late_text', 'deadline_text', 'attempt1_text']:
        if vars.get(k) is None:
            vars[k] = ''
    if vars.get('acc_product_id') is None:
        vars['acc_product_id'] = 'p1'
vars['acc_state'] = 'known' if known else 'unknown'
'''
assert "{{" not in FACTS_CODE and "}}" not in FACTS_CODE


def code_node(name, target, extra_transitions=()):
    return {
        "name": name, "node_type": "code", "passthrough": True, "passthrough_default_transition": target,
        "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
        "pre_actions": [{"type": "function", "function": {"name": "code_exec", "handler": "__function__:code_exec",
                         "parameters": {"type": "object", "properties": {
                             "code": {"type": "string", "default": FACTS_CODE},
                             "timeout_ms": {"type": "number", "default": 10000}}}}}],
        "transitions": list(extra_transitions) + [always(target)],
    }


# ---------------------------------------------------------------- tools
GET_ACCOUNT_POST = r'''try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if isinstance(d, dict):
            ps = d.get('products')
            if isinstance(ps, list) and len(ps) > 0 and isinstance(ps[0], dict):
                for k in ['product_id', 'type', 'card_last4', 'past_due', 'days_late', 'minimum_payment', 'instalment_amount']:
                    if ps[0].get(k) is not None:
                        d['p_' + k] = ps[0].get(k)
except Exception:
    pass
'''

get_account_action = {
    "type": "function",
    "config": {"timeoutMs": 12000, "maxRetries": 2},
    "function": {
        "name": "get_account", "handler": "__function__:api_call", "description": "Get the late products.",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string", "default": BASE + "/get_account"},
            "method": {"type": "string", "default": "POST"},
            "headers": HDR,
            "body": {"type": "object", "properties": {"customer_id": CID}, "required": []}}}},
    "post_process_code": GET_ACCOUNT_POST,
}

VERIFY_POST = r'''try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if not isinstance(d, dict):
            d = dict(ok=False, error='service unavailable')
            result['data'] = d
        def t(x):
            return str(x).lower() == 'true'
        wl = d.get('wrong_answers_left')
        try:
            wl = int(wl)
        except Exception:
            wl = None
        if d.get('hint') == 'day_month_swapped':
            msg = 'The day and the month look swapped. This does NOT count as a wrong answer. Ask the customer to say the date of birth again, with the month as a word (for example: the 3rd of April 1990).'
        elif t(d.get('all_verified')):
            msg = 'Both security answers are verified.'
        elif wl is not None and wl <= 0:
            msg = 'The security check has ended after three wrong answers. Do not ask anything more.'
        elif t(d.get('verified')):
            msg = 'That answer is correct. Now ask for the last four digits of the phone number on file (if that is not verified yet). Do not call verify_identity until the customer answers.'
        elif not t(d.get('ok')):
            msg = 'The answer could not be checked (' + str(d.get('error') or 'unreadable') + '). This does not count as a wrong answer. Ask the customer to repeat the same answer. Never send words or partial dates: date_of_birth must be YYYY-MM-DD.'
        else:
            msg = 'That answer did NOT match. Tell the customer it did not match and ask the SAME question again.'
        d['what_to_do_next'] = msg
except Exception:
    pass
'''

verify_tool = api_tool(
    "verify_identity", "/verify_identity",
    {"customer_id": CID,
     "field": {"type": "string", "enum": ["date_of_birth", "phone_last4"], "default": "{{vi_field}}",
               "description": "Which question was answered. One of: date_of_birth, phone_last4."},
     "answer": {"type": "string", "default": "{{vi_answer}}",
                "description": "For date_of_birth: the full date as YYYY-MM-DD (convert words; a numbers-only date is day, then month, then year). For phone_last4: exactly four digits."}},
    ["field", "answer"],
    "Check ONE security answer. CALL it every time the customer has given a complete answer to the question you asked (a full date of birth with day, month and year, or all four digits). Do not call it with a partial answer.",
    mapping=[{"path": "data.wrong_answers_left", "variable": "wrong_left"},
             {"path": "data.all_verified", "variable": "all_verified"}],
    post=VERIFY_POST)

PROMISE_POST = r'''try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if not isinstance(d, dict):
            d = dict(ok=False, error='service unavailable')
            result['data'] = d
        ok = str(d.get('ok')).lower() == 'true'
        d['ok'] = ok
        n = 0
        try:
            n = int(vars.get('promise_fail_n') or 0)
        except Exception:
            n = 0
        if ok:
            d['promise_state'] = 'recorded'
            d['what_to_do_next'] = 'The promise IS recorded.'
        else:
            n = n + 1
            try:
                vars['promise_fail_n'] = n
            except Exception:
                pass
            d['promise_failures'] = n
            if n >= 2:
                d['promise_state'] = 'failed_twice'
                d['what_to_do_next'] = 'The promise was NOT recorded, for the second time. Do not call create_promise again. Tell the customer you could not record the promise, then call transition_to_close_service_error.'
            else:
                d['promise_state'] = 'failed_once'
                d['what_to_do_next'] = 'The promise was NOT recorded. Do NOT say it is recorded. Call create_promise once more right now with exactly the same amount and date.'
except Exception:
    pass
'''

promise_tool = api_tool(
    "create_promise", "/create_promise",
    {"customer_id": CID,
     "product_id": {"type": "string", "default": "{{acc_product_id}}"},
     "amount": {"type": "number", "default": "{{promise_amount}}",
                "description": "The agreed amount, a number such as 420.0. Must be from the floor to the full past-due amount."},
     "date": {"type": "string", "format": "date", "default": "{{promise_date}}",
              "description": "The agreed date as YYYY-MM-DD. Must be a date marked ALLOWED in the calendar."}},
    ["amount", "date"],
    "Record the payment promise. CALL it only after you read back the product, amount and date, asked 'Do you confirm?' and the customer clearly said yes. Never call it twice for a promise that was recorded.",
    mapping=[{"path": "data.promise_state", "variable": "promise_state"},
             {"path": "data.promise_failures", "variable": "promise_failures"}],
    post=PROMISE_POST)


def transfer_tool(queue, desc):
    return api_tool(
        "transfer_" + queue, "/transfer_to_agent",
        {"customer_id": CID, "queue": {"type": "string", "enum": ["restructuring", "general", "support"], "default": queue}},
        [], desc,
        post=post_simple("The transfer is done. Say one short sentence that a colleague will take over.",
                         "The transfer did NOT work. Tell the customer you could not transfer the call."))


T_RESTR = transfer_tool("restructuring", "Transfer to the restructuring team. CALL it as soon as the customer asks for a new payment plan, lower instalments or to restructure the debt. Do not describe any plan yourself.")
T_GENERAL = transfer_tool("general", "Transfer to a human colleague. CALL it only when the customer asks for a human/real person a second time, after you asked once whether you can help.")
T_SUPPORT = transfer_tool("support", "Transfer to the customer support team. CALL it only when a customer in hardship (illness, death in the family, job loss) accepts your offer to connect them with customer support.")

callback_tool = api_tool(
    "schedule_callback", "/schedule_callback",
    {"customer_id": CID,
     "date": {"type": "string", "format": "date", "default": "{{cb_date}}", "description": "Callback date as YYYY-MM-DD."},
     "time": {"type": "string", "default": "{{cb_time}}", "description": "Callback time as HH:MM, 24-hour clock, for example 11:00."}},
    ["date", "time"],
    "Book a callback. CALL it as soon as the person names a day and time that is inside the allowed callback window.",
    post=post_simple("The callback is booked.", "The callback could NOT be booked. Say so honestly."))

# ---------------------------------------------------------------- prompts
SYSTEM = """You are Freya Bank's digital assistant on an outbound phone call. Speak English. Keep every turn to one to three short sentences. Be polite and calm.
Call facts: you are calling {{title}} {{first_name}} {{last_name}}. Address the customer as {{title}} {{last_name}}. Now: {{today_text}}. Use this date, never your own clock.
Rules that always hold:
- Tell the truth. Never invent figures, dates, reasons or policies. If you do not have some information, say you do not have that information.
- If asked whether you are a robot or an AI: say you are Freya Bank's digital assistant, then continue.
- If asked whether this is a scam: say they can verify the call by phoning Freya Bank's customer service number, then continue.
- Never offer a discount, a waiver, an instalment plan, a payment plan or any other term.
- Never say that something is recorded, booked or transferred unless the tool result says ok true.
- When a rule says to call a tool, call the tool; saying it is not enough. Call one tool per message. After every tool result, speak to the customer or call the next tool. Never end a turn with nothing. If a tool result has what_to_do_next, follow it.
- Never say goodbye yourself unless told to: the call is ended by the system."""

OPENING_TASK = """You have just said who you are and asked whether you are speaking with {{title}} {{last_name}}. Do not call any tool in this step.
Your only job is to find out who is on the line.
- Only "yes", "that's me", "speaking" or the customer's own name counts as confirmation. "Hello", "go ahead" or "who is this" do not.
- If the answer is not a confirmation, answer any question briefly (who you are: Freya Bank's digital assistant; robot/AI and scam rules), then ask again exactly: "Am I speaking with {{title}} {{last_name}}?"
- Do NOT say why you are calling. Never say collections, debt, payment, account, amount or any product. If asked what it is about, say you can only discuss it with {{title}} {{last_name}} in person.
- If the person says twice that they do not want to talk, call transition_to_close_declined."""

THIRD_PARTY_TASK = """The person on the line is NOT {{title}} {{last_name}}. Do not say why you are calling: never mention collections, debt, payment, an account, an amount or any product, even if they ask or offer to pay. Do not ask security questions. If they ask what it is about, say you can only discuss it with {{title}} {{last_name}}.
Your job: ask when {{title}} {{last_name}} can be reached.
{{callback_facts}}
- When the person names a day and time inside that window, call schedule_callback with the date (YYYY-MM-DD) and the time (HH:MM). If they say "morning around eleven", use 11:00. If they give a day but no time (or a time but no day), ask for the missing part.
- If the first day or time they offer is outside the window, say it is outside the times you can call and ask once for another time inside the window (today until 19:00 or the next business day from 10:00 to 19:00). If the second offer is also outside the window, do not schedule; call transition_to_close_no_callback.
- If they will not give any time, call transition_to_close_no_callback.
- If they say the number does not belong to {{title}} {{last_name}}, call transition_to_close_wrong_number.
- If they say {{title}} {{last_name}} has died, call transition_to_close_deceased at once without asking anything.
- After schedule_callback returns ok true, just say thank you; the system ends the call."""

IDENTITY_TASK = """The customer confirmed they are {{title}} {{last_name}}. Your job now is the security check. You have no account details yet, and you must not say why you are calling: never say collections, debt, payment, amount or the product in this step.
Ask two security questions, one at a time:
1. Date of birth. When the customer has given a full date (day, month and year), call verify_identity with field date_of_birth and the answer converted to YYYY-MM-DD. Spoken words such as "fourteenth of March nineteen eighty-eight" become 1988-03-14. A date given only as numbers is day, then month, then year: "05/03/1988" is 1988-03-05. If the customer gives the date in pieces, wait until you have day, month and year.
2. Then the last four digits of the phone number on file. Call verify_identity with field phone_last4 and exactly four digits.
Follow what_to_do_next in every verify_identity result. A wrong answer may be asked again. If the result says the day and month look swapped, ask the customer to say the month as a word.
If the customer does not want to answer, or asks what the call is about instead of answering: the first time, explain once that these questions protect their account, and ask again. If they refuse again or ask again what it is about, call transition_to_close_declined. If the customer says twice that they do not want to talk, call transition_to_close_declined.
If the customer asks for a human: the first time, ask whether you can help first. If they insist, call transfer_general.
Robot/AI and scam questions: answer as in the general rules, then repeat the security question."""

NEGOTIATE_TASK = """The customer is verified. You have already told them: you are calling from the collections team about a late payment on their {{product_phrase}}, the past-due amount {{past_due_text}}, {{days_late_text}} days late, and asked "Can you make this payment today?".

ACCOUNT AND DATE FACTS (computed by the bank; trust them, do not calculate dates yourself):
{{deal_facts}}

TOOLS AND EXITS (call the tool; saying it is not enough):
- create_promise: after the read-back and a clear yes.
- transition_to_close_paid: the customer says they already paid this past-due amount. First say that payments can take one business day to appear, in the same message. Take no promise.
- transition_to_close_dispute: the customer says the debt is not theirs, they never had this product, or the product was closed or paid off in the past. Do not argue. Take no promise.
- transfer_restructuring: the customer asks for a new payment plan, lower instalments or restructuring. Do not describe any plan.
- transfer_support: hardship customer accepts your offer of the customer support team.
- transition_to_close_hardship: hardship customer declines the support team (and names no date or amount themselves).
- transfer_general: the customer asks for a human a second time, after you asked once whether you can help.
- transition_to_close_refused: the persuasion attempts are used up, or the customer said twice they do not want to talk.
- transition_to_close_service_error: create_promise failed twice.

HOW TO GET THE PROMISE
1. The first ask (already made) is for the FULL amount today. Never ask "how much can you pay?", "what amount can you manage?" or "please tell me the amount". You propose every amount: every offer you make names BOTH the amount and the date, for example "Can you pay {{past_due_text}} on Friday 23 October 2026?".
   When the customer accepts or names a date without naming an amount, the amount is the full past-due amount {{past_due_text}} (or the floor {{floor_text}} if they already said the full amount is too much and accepted the floor). Do not ask for an amount; go straight to the read-back.
   When the customer says "yes" to an offer you made, the promise is exactly that offer (amount and date); go straight to the read-back.
2. A date or an amount the customer proposes is never a refusal. Check it:
   - Date: must be ALLOWED in the calendar (today or later, a business day, not after the deadline). A weekend or holiday not after the deadline: offer the next business day shown in the calendar. A date after the deadline: say the latest date you can record is the deadline ({{deadline_text}}) and offer the amount on that date (full amount {{past_due_text}}, or the floor if they already said the full amount is too much); if they refuse the deadline, that is a flat refusal.
   - Vague period ("next week", "the week after next", "end of the month", "when my salary comes"): ask once for the exact day. If they still give none, propose the deadline.
   - "this <weekday>" and "next <weekday>": use the WEEKDAY WORDS table.
   - Amount: from the floor up to the full amount (both included) is accepted. Below the floor: say it cannot be recorded and offer the floor once; if they do not accept, that is a flat refusal.
   - If they say the full amount is too much: offer the floor amount {{floor_text}} once, and say the rest stays overdue. If they refuse the floor, that is a flat refusal.
   - If the customer gave an amount but no date, or a date but no amount, the missing part defaults to: amount = full amount (or floor if they said the full amount is too much); ask for the date if missing ("today" was already asked).
3. Flat refusal: a no without any date or amount (for example "no, I can't pay today"), or a non-answer. Each flat refusal uses one persuasion attempt, in this order:
   - Attempt 1: offer the amount (full, or floor if they said the full amount is too much) on the attempt 1 date from the facts.
   - Attempt 2 (only if 2 attempts are allowed): offer the floor {{floor_text}} on the deadline {{deadline_text}}.
   When the attempts are used up and the customer refuses again, call transition_to_close_refused. Never repeat an offer the customer already refused.
4. Hardship (illness, a death in the family, job loss): say one short sentence of sympathy, make NO persuasion attempt, and offer to connect them with the customer support team. If they accept, call transfer_support. If they decline, call transition_to_close_hardship. This comes before refusals and plan requests. If they still name a date or an amount themselves, handle it as a promise.
5. Confirm: read back the product, the amount and the date, e.g. "So that is 420.00 for your credit card ending 4821 on Friday 16 October 2026. Do you confirm?" Call create_promise only after a clear yes. If they change the date or the amount, check it again and read back again.
6. create_promise results: if it failed, do NOT say it is recorded; follow what_to_do_next (retry once with the same values; after a second failure say you could not record the promise and call transition_to_close_service_error). When it succeeds, the system takes over: say nothing more than a short thanks if you must speak.
7. A recorded promise cannot be changed or cancelled in this call; they can change it in the mobile app.
8. If the customer asks for a human the first time, ask whether you can help first.
9. Questions you cannot answer from these facts (interest, fees, why it is late, balance beyond the past-due amount): say you do not have that information."""

ACCOUNT_STATEMENT = ("Thank you, {{title}} {{last_name}}, you are verified. I am calling from the collections team about a late payment "
                     "on your {{product_phrase}}. The past-due amount is {{past_due_text}}, and it is {{days_late_text}} days late. "
                     "Can you make this payment today?")

# ---------------------------------------------------------------- close nodes
CLOSES = {
    "close_promise": ("promise", None, "Your promise is recorded. You will receive a text message confirming this promise. Thank you for your time, {{title}} {{last_name}}. Goodbye."),
    "close_paid": ("paid", None, "Thank you. Payments can take one business day to appear, so I will not take a promise today. Thank you for your time, {{title}} {{last_name}}. Goodbye."),
    "close_transferred_restructuring": ("transferred", "restructuring", "I am transferring you to our restructuring team now. Thank you for your time, {{title}} {{last_name}}. Goodbye."),
    "close_transferred_human": ("transferred", "human", "I am transferring you to a colleague now. Thank you for your time, {{title}} {{last_name}}. Goodbye."),
    "close_transferred_support": ("transferred", "support", "I am transferring you to our customer support team now. Thank you for your time, {{title}} {{last_name}}. Goodbye."),
    "close_refused": ("no_promise", "refused", "I understand. Thank you for your time, {{title}} {{last_name}}. Goodbye."),
    "close_hardship": ("no_promise", "hardship", "I understand. Thank you for your time, {{title}} {{last_name}}. Goodbye."),
    "close_dispute": ("no_promise", "dispute", "I understand, I will not take a payment promise today. Thank you for your time, {{title}} {{last_name}}. Goodbye."),
    "close_service_error": ("no_promise", "service_error", "I am sorry, I could not record your promise because of a technical problem. Thank you for your time, {{title}} {{last_name}}. Goodbye."),
    "close_account_error": ("no_promise", "service_error", "I am sorry, I cannot access the account details right now because of a technical problem. Thank you for your time, {{title}} {{last_name}}. Goodbye."),
    "close_id_failed": ("not_verified", "failed", "I am sorry, I could not verify your identity, so I cannot continue this call. Please use the Freya Bank mobile app or visit a branch. Thank you for your time. Goodbye."),
    "close_declined": ("not_verified", "declined", "I understand. Thank you for your time. Goodbye."),
    "close_callback": ("not_reached", "callback", "Thank you, we will call back then. Goodbye."),
    "close_no_callback": ("not_reached", "no_callback", "Thank you for your time. Goodbye."),
    "close_wrong_number": ("not_reached", "wrong_number", "I am sorry for the trouble. Thank you, goodbye."),
    "close_deceased": ("not_reached", "deceased", "I am sorry for your loss. Thank you, goodbye."),
    "close_unclear": ("not_reached", "unclear", "Thank you for your time. Goodbye."),
}


def close_node(name, outcome, reason, text):
    body = {"customer_id": CID, "outcome": {"type": "string", "default": outcome}}
    if reason:
        body["reason"] = {"type": "string", "default": reason}
    action = {
        "type": "function",
        "config": {"timeoutMs": 12000, "maxRetries": 0},
        "function": {"name": "close_call", "handler": "__function__:api_call", "description": "End the call record.",
                     "parameters": {"type": "object", "properties": {
                         "url": {"type": "string", "default": BASE + "/close_call"},
                         "method": {"type": "string", "default": "POST"},
                         "headers": HDR,
                         "body": {"type": "object", "properties": body, "required": []}}}},
    }
    return {
        "name": name, "node_type": "api_request", "passthrough": True, "passthrough_default_transition": "end",
        "on_enter": {"type": "tts", "text": text}, "disable_inactivity_monitor": True,
        "pre_actions": [action], "transitions": [always("end")],
    }


def conv(name, task, tools, transitions, on_enter=None, extraction=None, max_turns=40, max_target="close_refused"):
    n = {"name": name, "node_type": "conversation", "task_message": task, "tools": tools,
         "transitions": transitions, "max_node_turns": max_turns, "max_turn_transition": max_target}
    if on_enter:
        n["on_enter"] = on_enter
        n["on_enter_first_entry_only"] = True
    if extraction:
        n["extraction_schema"] = extraction
    return n


def transfer_transitions():
    return [go("close_transferred_restructuring", "restructuring transfer done", cond_true("transfer_restructuring_response.data.ok")),
            go("close_transferred_human", "human transfer done", cond_true("transfer_general_response.data.ok")),
            go("close_transferred_support", "support transfer done", cond_true("transfer_support_response.data.ok"))]


nodes = {}
nodes["prepare"] = code_node("prepare", "opening")

nodes["opening"] = conv(
    "opening", OPENING_TASK, [],
    [go("identity", "the customer confirmed", [{"variable": "contact", "operator": "equals", "operand": "confirmed"}]),
     go("close_deceased", "the customer has died", [{"variable": "contact", "operator": "equals", "operand": "deceased"}]),
     go("close_wrong_number", "wrong number", [{"variable": "contact", "operator": "equals", "operand": "wrong_number"}]),
     go("third_party", "someone else answered", [{"variable": "contact", "operator": "equals", "operand": "third_party"}]),
     go("close_unclear", "still unclear after the second ask",
        [{"logic": "and", "conditions": [{"variable": "contact", "operator": "equals", "operand": "unclear"},
                                         {"variable": "opening.current_turns", "operator": "greater_than", "operand": 1}]}]),
     tool_go("close_declined", "The person said twice that they do not want to talk"),
     always("opening")],
    on_enter={"type": "tts", "text": "Hello, I am a digital assistant calling from Freya Bank. Please note that we record this call. Am I speaking with {{title}} {{last_name}}?"},
    extraction=[{"name": "contact", "type": "string",
                 "enum_values": ["confirmed", "third_party", "wrong_number", "deceased", "unclear"],
                 "description": ("Who answered, judged from the person's LATEST message only. confirmed: they said yes / that's me / speaking / "
                                 "their own name ({{first_name}} or {{last_name}}). third_party: they say they are someone else (a relative, "
                                 "partner, colleague) or that {{title}} {{last_name}} is not available / not home. wrong_number: the number "
                                 "does not belong to that person / they do not know them. deceased: they say {{title}} {{last_name}} has died. "
                                 "unclear: anything else, e.g. hello, go ahead, who is this, what is this about, are you a robot."),
                 "min_confidence": 0.5}],
    max_turns=3, max_target="close_unclear")

nodes["third_party"] = conv(
    "third_party", THIRD_PARTY_TASK, [callback_tool],
    [go("close_callback", "callback booked", cond_true("schedule_callback_response.data.ok")),
     tool_go("close_no_callback", "No callback time inside the window after asking once more, or no time given"),
     tool_go("close_wrong_number", "The number does not belong to the customer"),
     tool_go("close_deceased", "The customer has died")],
    max_turns=12, max_target="close_no_callback")

nodes["identity"] = conv(
    "identity", IDENTITY_TASK, [verify_tool, T_GENERAL],
    [go("load_account", "both security answers verified",
        cond_true("all_verified") + cond_true("verify_identity_response.data.all_verified")),
     go("close_id_failed", "three wrong answers",
        [{"variable": "wrong_left", "operator": "equals", "operand": "0"},
         {"variable": "verify_identity_response.data.wrong_answers_left", "operator": "equals", "operand": "0"}]),
     go("close_transferred_human", "human transfer done", cond_true("transfer_general_response.data.ok")),
     tool_go("close_declined", "The customer refused the security questions a second time, or said twice they do not want to talk")],
    on_enter={"type": "tts", "text": "Thank you. Before we continue, I need to ask two short security questions. What is your date of birth?"},
    max_turns=20, max_target="close_declined")

nodes["load_account"] = {
    "name": "load_account", "node_type": "api_request", "passthrough": True, "passthrough_default_transition": "account_facts",
    "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True, "suppress_tool_results": True,
    "pre_actions": [get_account_action],
    "response_mapping": [{"path": "data.products", "variable": "products"}] + [
        {"path": "data.p_" + k, "variable": "acc_" + k} for k in
        ["product_id", "type", "card_last4", "past_due", "days_late", "minimum_payment", "instalment_amount"]],
    "transitions": [always("account_facts")],
}

nodes["account_facts"] = code_node(
    "account_facts", "negotiate",
    [go("close_account_error", "account not available", [{"variable": "acc_state", "operator": "equals", "operand": "unknown"}])])

nodes["negotiate"] = conv(
    "negotiate", NEGOTIATE_TASK, [promise_tool, T_RESTR, T_SUPPORT, T_GENERAL],
    [go("close_promise", "promise recorded",
        [{"variable": "promise_state", "operator": "equals", "operand": "recorded"}] + cond_true("create_promise_response.data.ok")),
     go("close_service_error", "promise failed twice",
        [{"variable": "promise_state", "operator": "equals", "operand": "failed_twice"},
         {"variable": "promise_failures", "operator": "greater_than", "operand": 1},
         {"variable": "create_promise_failure_count", "operator": "greater_than", "operand": 1}]),
     *transfer_transitions(),
     tool_go("close_paid", "The customer says they already paid this past-due amount"),
     tool_go("close_dispute", "The customer says the debt is not theirs or the product was closed or paid off in the past"),
     tool_go("close_hardship", "Hardship customer declined the support team"),
     tool_go("close_refused", "Persuasion attempts used up, or the customer said twice they do not want to talk"),
     tool_go("close_service_error", "create_promise failed twice")],
    on_enter={"type": "tts", "text": ACCOUNT_STATEMENT},
    max_turns=40, max_target="close_refused")

for k, (o, r, txt) in CLOSES.items():
    nodes[k] = close_node(k, o, r, txt)

nodes["end"] = {
    "name": "end", "node_type": "end_call", "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
    "transitions": [],
    "terminal": {"type": "function", "function": {"name": "call_closed", "handler": "__function__:end_call",
                 "parameters": {"type": "object", "properties": {"message_mode": {"type": "string", "default": "none"}}}}},
}

wf = {
    "initial_node": "prepare",
    "system_prompt": SYSTEM,
    "nodes": nodes,
    "global_nodes": {},
    "test_variables": {"customer_id": "c_test", "first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-14T11:00"},
}
OUT.write_text(json.dumps(wf, indent=1))
print("wrote", OUT)
