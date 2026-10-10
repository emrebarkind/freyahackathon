"""Local end-to-end harness for the in-agent engine: a fake bank + scripted customer turns.

A script is a list of extraction results (what the talk node's extractor would produce for each customer
turn): dict(u_kind=..., u_text=..., u_date=..., u_amount=..., u_scope=...). The harness runs the engine
exactly as the workflow would (step -> api nodes -> step -> talk ...) and returns the ledger + transcript.
"""
import copy
import json
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from builder.runtime import cal, engine  # noqa: E402


class FakeBank:
    def __init__(self, case):
        self.case = case
        self.ident = case["identity"]
        self.products = [dict(p, product_id="p%d" % (i + 1)) for i, p in enumerate(case["products"])]
        self.faults = {f["tool"]: f["fail_first_n"] for f in case.get("faults", [])}
        self.led = dict(promises=[], notes=[], callbacks=[], transfers=[], outcome=None, reason=None, calls=[])
        self.verified = {}
        self.wrong = 0

    def __call__(self, tool, body):
        if self.faults.get(tool, 0) > 0:
            self.faults[tool] -= 1
            self.led["calls"].append(dict(tool=tool, args=body, result=dict(error="500")))
            return 500, None
        fn = getattr(self, tool)
        r = fn(**{k: v for k, v in body.items() if k != "customer_id"})
        self.led["calls"].append(dict(tool=tool, args=body, result=r))
        return 200, r

    def verify_identity(self, field, answer):
        if self.wrong >= 3:
            return dict(ok=False, error="identity check ended")
        exp = self.ident.get(field)
        if field == "date_of_birth":
            if not cal.re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(answer)):
                return dict(ok=False, error="unreadable date")
            y, m, d = answer.split("-")
            if answer != exp and "%s-%s-%s" % (y, d, m) == exp:
                return dict(ok=True, verified=False, wrong_answers_left=3 - self.wrong, hint="day_month_swapped")
        if str(answer) == str(exp):
            self.verified[field] = True
            return dict(ok=True, verified=True, wrong_answers_left=3 - self.wrong, all_verified=len(self.verified) == len(self.ident))
        self.wrong += 1
        return dict(ok=True, verified=False, wrong_answers_left=3 - self.wrong, all_verified=False)

    def get_account(self):
        if len(self.verified) < len(self.ident):
            return dict(ok=False, error="identity not verified")
        return dict(ok=True, products=copy.deepcopy(self.products))

    def create_promise(self, product_id, amount, date):
        if len(self.verified) < len(self.ident):
            return dict(ok=False, error="identity not verified")
        self.led["promises"].append(dict(product_id=product_id, amount=float(amount), date=date))
        return dict(ok=True, promise_id="pr%d" % len(self.led["promises"]))

    def add_note(self, product_id, reason, text=""):
        self.led["notes"].append(dict(product_id=product_id, reason=reason))
        return dict(ok=True)

    def schedule_callback(self, date, time):
        self.led["callbacks"].append(dict(date=date, time=time))
        return dict(ok=True)

    def transfer_to_agent(self, queue):
        self.led["transfers"].append(dict(queue=queue))
        return dict(ok=True)

    def close_call(self, outcome, reason=None):
        self.led["outcome"], self.led["reason"] = outcome, (reason or None)
        return dict(ok=True)


API = {  # node -> (tool, body builder)
    "api_verify": ("verify_identity", lambda V: dict(field=V["q_field"], answer=V["q_answer"])),
    "api_account": ("get_account", lambda V: dict()),
    "api_promise": ("create_promise", lambda V: dict(product_id=V["p_product"], amount=V["p_amount"], date=V["p_date"])),
    "api_note": ("add_note", lambda V: dict(product_id=V["n_product"], reason=V["n_reason"])),
    "api_callback": ("schedule_callback", lambda V: dict(date=V["cb_date"], time=V["cb_time"])),
    "api_transfer": ("transfer_to_agent", lambda V: dict(queue=V["t_queue"])),
    "api_close": ("close_call", lambda V: dict(outcome=V["c_outcome"], reason=V["c_reason"])),
    "api_close_nr": ("close_call", lambda V: dict(outcome=V["c_outcome"])),
}


def flatten(prefix, obj, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            flatten(prefix + "." + k, v, out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            flatten(prefix + "." + str(i), v, out)
    else:
        out[prefix] = ("true" if obj is True else "false" if obj is False else obj)


def feed(V, stage, u):
    V.update({stage + "_kind": u.get("k", "none"), stage + "_text": u.get("t", ""), stage + "_date": u.get("d", ""),
              stage + "_amount": u.get("a", ""), stage + "_side": u.get("side", "none"),
              stage + "_for": u.get("f", "none"), stage + "_cut": u.get("cut", "no")})


def run_case(spec, case, script, verbose=False, openapi=None):
    """Runs the call through the compiled workflow (selftest.walk): engine runs, request bodies and transitions
    (including planned chains) as on the platform."""
    from builder import selftest, compile as comp
    openapi = openapi or json.load(open(ROOT / "kit" / "build-the-builder" / "tools" / "openapi.json"))
    spec = comp.apply_defaults(json.loads(json.dumps(spec)), openapi)
    wf = comp.compile_workflow(spec, openapi)
    bank = FakeBank(case)
    V = dict(case["variables"], customer_id="c_x")

    def call(tool, body, slots):
        code, r = bank(tool, body)
        return r

    tr = selftest.walk(wf, spec, V, call, script, lambda stage, u: feed(V, stage, u))
    opening = (spec["lines"]["opening"] + " " + spec["lines"]["confirm_ask"]).replace("{title}", V.get("title", "")).replace("{last_name}", V.get("last_name", ""))
    tr[0] = ("agent", opening)
    if verbose:
        for who, text in tr:
            print(("  AGENT: " if who == "agent" else "  CUST:  ") + str(text))
    return bank.led, tr
