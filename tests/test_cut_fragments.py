"""A customer whose messages keep arriving cut off (talkative persona, PUB-13 on the platform, 11 Oct): the plan read
back is kept through any number of unanswered confirmations, and "please go on" stays bounded over the whole call."""
import json, pathlib
from builder import selftest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC = json.load(open(ROOT / "eval" / "clean-runs" / "cand7-ab" / "cand7-ab.spec.json"))
OPENAPI = json.load(open(ROOT / "kit" / "build-the-builder" / "tools" / "openapi.json"))
CASE = [c for c in json.load(open(ROOT / "kit" / "build-the-builder" / "public-test-set.json")) if c["id"] == "PUB-13"][0]
FRAG = dict(k="unclear", t="I have been dealing with so many emails this", d="", a="", f="none", side="none", cut="yes")


def run(nego, after):
    products = [dict(p, product_id=f"p{i + 1}") for i, p in enumerate(CASE["products"])]
    bank = selftest.GenericBank(json.loads(json.dumps(SPEC)), CASE["identity"], products)
    turns = [dict(k="confirmed", t="yes that's me"), dict(k="answer", t="the eighth of January 1991", norm="1991-01-08"),
             dict(k="answer", t="6604", norm="6604")] + nego + after
    led, tr = selftest.simulate(SPEC, dict(customer_id="c", **CASE["variables"]), bank, turns, openapi=OPENAPI, max_steps=4000)
    return led, [x[1] for x in tr if x[0] == "agent"]


BOTH_30 = [dict(k="proposes", t="I cannot pay today, but I want to pay both on the 30th of October", d="the 30th of October",
                a="", f="all", side="none", cut="no")]


def test_unanswered_readback_keeps_the_plan():
    led, said = run(BOTH_30, [FRAG] * 16 + [dict(k="yes", t="Yes, I confirm.", d="", a="", f="none", side="none", cut="no")])
    assert sorted(led["promises"]) == [("p1", 300.0, "2026-10-30"), ("p2", 900.0, "2026-10-23")]
    assert led["outcome"] == "promise"
    assert not any("16 October" in x for x in said)              # never back to the first offer of the ladder


def test_go_on_is_bounded_over_the_call():
    _, said = run(BOTH_30, [FRAG] * 30)
    assert sum("please go on" in x.lower() for x in said) == 4
    _, said = run([FRAG] * 30, [])
    assert sum("please go on" in x.lower() for x in said) == 4
