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


def with_rule(value):
    s = json.loads(json.dumps(SPEC))
    s.setdefault("rules", {})["non_answer_counts"] = value
    return s


def run_spec(spec, nego, after):
    global SPEC
    keep, SPEC = SPEC, spec
    try:
        return run(nego, after)
    finally:
        SPEC = keep


SMALL_TALK = dict(k="unclear", t="Traffic was terrible this morning, the office is chaos.", d="", a="", f="none", side="none", cut="no")
NO = dict(k="no", t="No, I can't.", d="", a="", f="none", side="none", cut="no")
YES = dict(k="yes", t="Yes, I confirm.", d="", a="", f="none", side="none", cut="no")


def test_silence_is_not_a_refusal_unless_the_brief_says_so():
    led, said = run_spec(with_rule(False), [SMALL_TALK] * 30, [])
    assert led["notes"] == [] and led["outcome"] is None and led["promises"] == []   # nothing invented
    assert "close_call" not in led["calls"]


def test_with_the_briefs_rule_empty_turns_end_the_call_as_used_up_attempts():
    led, said = run_spec(with_rule(True), [SMALL_TALK] * 30, [])
    assert led["outcome"] == "no_promise" and led["promises"] == []
    assert sorted(led["notes"]) == [("p1", "refused"), ("p2", "refused")]
    assert led["calls"].count("close_call") == 1
    assert len(said) <= 3 + 12 + 2                                # bounded: greeting, identity, at most 12 empty turns


def test_with_the_briefs_rule_an_unconfirmed_plan_is_never_recorded():
    led, said = run_spec(with_rule(True), BOTH_30, [FRAG] * 30)
    assert led["promises"] == [] and led["outcome"] == "no_promise"
    led, said = run_spec(with_rule(True), BOTH_30, [FRAG] * 10 + [YES])
    assert sorted(led["promises"]) == [("p1", 300.0, "2026-10-30"), ("p2", 900.0, "2026-10-23")]


def test_an_explicit_no_is_still_a_refusal_and_a_question_is_not():
    led, _ = run_spec(with_rule(False), [NO] * 6, [])
    assert led["outcome"] == "no_promise" and ("p1", "refused") in led["notes"]
