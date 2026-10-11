"""Engine-level probe of ambiguous customer turns (extraction outputs supplied by hand: this proves engine behaviour
only, not what the platform's extraction model would produce). Specs: candidate 8's own A and A+B builds.
    python3 eval/ambiguity/engine_probe.py"""
import copy, json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from builder import selftest
OA = json.load(open(ROOT / "kit/build-the-builder/tools/openapi.json"))
CASES = {c["id"]: c for c in json.load(open(ROOT / "kit/build-the-builder/public-test-set.json"))}
SA = json.load(open(ROOT / "eval/clean-runs/cand8-a/cand8-a.spec.json"))
SB = json.load(open(ROOT / "eval/clean-runs/cand8-ab/cand8-ab.spec.json"))

def T(k="unclear", t="", d="", a="", f="none", cut="no", side="none"):
    return dict(k=k, t=t, d=d, a=a, f=f, cut=cut, side=side)

def ident(case):
    i = case["identity"]
    return [T("confirmed", "yes that's me"), dict(k="answer", t=str(i["date_of_birth"]), norm=i["date_of_birth"]),
            dict(k="answer", t=str(i["phone_last4"]), norm=str(i["phone_last4"]))]

def run(spec, cid, turns, na=None):
    s = copy.deepcopy(spec)
    if na is not None:
        s.setdefault("rules", {})["non_answer_counts"] = na
    c = CASES[cid]
    prods = [dict(p, product_id=f"p{i+1}") for i, p in enumerate(c["products"])]
    bank = selftest.GenericBank(copy.deepcopy(s), c["identity"], prods)
    led, tr = selftest.simulate(s, dict(customer_id="c", **c["variables"]), bank, ident(c) + turns, openapi=OA, max_steps=4000)
    said = [x[1] for x in tr if x[0] == "agent"]
    return led, said

UH = T("unclear", "uh...", cut="no"); AAA = T("unclear", "aaa...", cut="yes"); HMM = T("none", "hmm...")
SAL = T("unclear", "my salary...", cut="yes"); THINK = T("unclear", "I was thinking...", cut="yes")
LEAK = T("unclear", "thought\nThe user is asking for the last four", cut="yes")      # leaked persona reasoning: malformed
YES = T("yes", "Yes, I confirm."); NO = T("no", "No, I won't do that.")
rows = []
def probe(name, spec, cid, turns, na=None, expect=""):
    led, said = run(spec, cid, turns, na)
    rows.append(dict(name=name, na=na if na is not None else spec["rules"].get("non_answer_counts"),
                     promises=led["promises"], notes=led["notes"], outcome=(led["outcome"], led["reason"]),
                     closed="close_call" in led["calls"], writes=[c for c in led["calls"] if c in ("create_promise", "add_note")],
                     agent_turns=len(said), go_on=sum("go on" in x.lower() for x in said), last=said[-1][:110] if said else "",
                     expect=expect))

# PUB-01: 420 card, now Wed 14 Oct (A).  PUB-13: card 300 + loan 900 (B).
probe("filler x30, brief counts non-answers", SA, "PUB-01", [UH, AAA, HMM] * 10, expect="bounded; close only by brief rule (no_promise/refused); nothing written but the refusal close")
probe("filler x30, brief silent", SA, "PUB-01", [UH, AAA, HMM] * 10, na=False, expect="no refusal, no close, nothing written")
probe("leaked reasoning x20, brief silent", SA, "PUB-01", [LEAK] * 20, na=False, expect="treated as malformed: no intent, nothing written")
probe("incomplete then date", SA, "PUB-01", [SAL, T("proposes", "my salary comes Friday so I can pay the full amount Friday", d="Friday"), YES],
      expect="promise 420 on Fri 16 Oct after yes")
probe("fragmented date across messages", SA, "PUB-01", [T("unclear", "I can pay on", cut="yes"), T("proposes", "Friday.", d="Friday"), YES],
      expect="promise on Fri 16 Oct")
probe("fragmented amount (cut value) then rest", SA, "PUB-01", [T("proposes", "I can pay three hundred and", a=300.0, cut="yes"),
      T("proposes", "fifty on Friday", a=350.0, d="Friday"), YES], expect="promise 350 on Fri 16 Oct (>= floor)")
probe("correction inside one message", SA, "PUB-01", [T("no", "Yes, no, Friday does not work.", d="Friday")],
      expect="not an acceptance; nothing written yet")
probe("unrelated sentence then useful date", SA, "PUB-01", [T("proposes", "Traffic was awful. I can pay the full amount on the 20th.", d="the 20th"), YES],
      expect="promise 420 on Tue 20 Oct")
probe("switch product while proposal pending", SB, "PUB-13", [T("no", "No, not today."), T("proposes", "For the loan I can pay on the 23rd.", d="the 23rd", f="personal_loan"),
      T("proposes", "And the card on the 30th.", d="the 30th", f="credit_card"), YES], expect="loan 900 23 Oct, card 300 30 Oct")
probe("unclear confirmations then yes", SA, "PUB-01", [T("pay_today", "I can pay the full amount today."), UH, THINK, HMM, YES],
      expect="one promise 420 today, written only after yes")
probe("unclear confirmations then explicit no", SA, "PUB-01", [T("pay_today", "I can pay the full amount today."), UH, THINK, HMM, NO],
      expect="nothing written for the plan; no as refusal of the plan per brief")
probe("incomplete forever after plan, brief counts", SB, "PUB-13", [T("proposes", "Both on the 30th of October.", d="the 30th of October", f="all")] + [AAA] * 30,
      expect="no promise without yes; bounded; close by brief rule")
probe("incomplete forever after plan, brief silent", SB, "PUB-13", [T("proposes", "Both on the 30th of October.", d="the 30th of October", f="all")] + [AAA] * 30, na=False,
      expect="no promise; plan kept; no close")
probe("same question asked 4x, brief silent", SA, "PUB-01", [T("question", "Why is it so much?")] * 4, na=False,
      expect="a question is not a refusal: no attempt consumed, no refused close")
probe("question alternating with fragments x20, brief counts", SA, "PUB-01", [T("question", "What?"), AAA] * 20,
      expect="bounded over the call?")
for r in rows:
    print(json.dumps(r, ensure_ascii=False))
