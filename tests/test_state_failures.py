"""Conversation state combined with API failures (Phase 2, step 7), through the compiled workflow and the generic bank.
A failed call returns nothing and records nothing (the kit API: "The service failed. Nothing was recorded. The call
may be repeated."). A write whose answer is lost after it was recorded is NOT documented; test C only shows what the
agent does then (it repeats the write), it does not claim the platform behaves that way."""
import copy
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from builder import compile as comp, selftest  # noqa: E402

O = json.load(open(ROOT / "kit" / "build-the-builder" / "tools" / "openapi.json"))
S = comp.apply_defaults(json.load(open(ROOT / "submission" / "brief-b.spec.json")), O)
IDENT, _ = selftest.identity_values(S)
P = [{"product_id": "p1", "type": "credit_card", "past_due": 300.0, "days_late": 5, "min_payment": 90.0},
     {"product_id": "p2", "type": "personal_loan", "past_due": 500.0, "days_late": 5, "min_payment": 100.0}]
BOTH = [{"k": "no"}, {"k": "proposes", "f": "credit_card", "d": "2026-10-16", "a": 300.0},
        {"k": "proposes", "f": "personal_loan", "d": "2026-10-16", "a": 500.0}, {"k": "yes"}, {"k": "no"}, {"k": "no"}]


def run(script, faults=None, prods=P, idturns=None):
    bank = selftest.GenericBank(S, IDENT, copy.deepcopy(prods), faults or {})
    turns = [dict(k="confirmed", t="yes")] + (idturns if idturns is not None else
                                               [dict(k="answer", t=IDENT[q["field"]]) for q in S["identity"]["questions"]])
    turns += [dict(dict(t=x["k"], d="", a=None, f="none", cut="no"), **x) for x in script]
    led, tr = selftest.simulate(S, dict(customer_id="c", first_name="A", last_name="M", title="Mr", now="2026-10-14T11:00"),
                                bank, turns, openapi=O)
    assert led["calls"][-1] == "close_call" and len(led["calls"]) < 40          # bounded, always closed
    return led, " ".join(t for w, t in tr if w == "agent")


def test_a_second_product_failed_write_keeps_the_first_and_claims_nothing_for_it():
    led, said = run(BOTH, faults={"create_promise:p2": 2})
    assert led["promises"] == [("p1", 300.0, "2026-10-16")]               # written once, not repeated in recovery
    assert led["notes"] == [("p2", "service_error")]
    assert "personal loan: I'm sorry, I could not record" in said and "Your promise is recorded" not in said


def test_one_failure_then_success_writes_each_promise_once():
    led, _ = run(BOTH, faults={"create_promise:p2": 1})
    assert sorted(led["promises"]) == [("p1", 300.0, "2026-10-16"), ("p2", 500.0, "2026-10-16")]


def test_lost_answer_after_a_write_is_repeated_documented_as_uncertain():
    led, _ = run(BOTH, faults={"create_promise:lost": 1})
    assert led["promises"].count(("p1", 300.0, "2026-10-16")) == 2       # what the agent does; platform semantics unknown


def test_a_corrected_date_stays_with_its_product_after_a_switch():
    led, said = run([{"k": "no"}, {"k": "proposes", "f": "credit_card", "d": "2026-10-16", "a": 300.0},
                     {"k": "proposes", "f": "credit_card", "d": "2026-10-19"}, {"k": "no"}, {"k": "yes"}, {"k": "no"}, {"k": "no"}])
    assert ("p1", 300.0, "2026-10-19") in led["promises"] and not any(p[0] == "p2" for p in led["promises"])
    assert "16 October" not in said.split("Let me read that back")[-1].split("Do you confirm")[0].split("Personal")[0]


def test_a_refusal_then_an_alternative_date():
    led, _ = run([{"k": "no"}, {"k": "proposes", "d": "2026-10-19"}, {"k": "yes"}, {"k": "no"}], prods=P[:1])
    assert led["promises"] == [("p1", 300.0, "2026-10-19")] and led["outcome"] == S["events"]["promise"]["outcome"]


def test_late_hardship_after_two_products_offers_the_agreed_promise_and_writes_nothing_unconfirmed():
    led, said = run([{"k": "no"}, {"k": "proposes", "f": "credit_card", "d": "2026-10-16", "a": 300.0},
                     {"k": "hardship"}, {"k": "no"}, {"k": "no"}])
    assert led["promises"] == [] and led["outcome"] == S["events"]["hardship"]["outcome"]
    assert "sorry to hear" in said


def test_partial_identity_answers_and_corrections():
    dob = IDENT[S["identity"]["questions"][0]["field"]]
    led, _ = run([{"k": "no"}, {"k": "no"}], prods=P[:1],
                 idturns=[dict(k="answer", t="the twenty first of June"), dict(k="answer", t="1985"),
                          dict(k="answer", t="77"), dict(k="answer", t="sorry, 7777")])
    assert led["calls"].count("verify_identity") == 2 and "get_account" in led["calls"]
    led, said = run([{"k": "no"}, {"k": "no"}], prods=P[:1],
                    idturns=[dict(k="answer", t=dob), dict(k="answer", t="7778"), dict(k="answer", t="7777")])
    assert led["calls"].count("verify_identity") == 3 and "does not match" in said and "get_account" in led["calls"]


def test_the_brief_may_rank_product_endings_for_the_close():
    global S
    saved = S
    try:
        P2 = [dict(P[0], product_id="p1"), dict(P[1], product_id="p2")]
        script = [{"k": "no"}, {"k": "dispute"}, {"k": "no"}, {"k": "no"}, {"k": "no"}, {"k": "no"}]
        led, _ = run(script, prods=P2)
        first = led["outcome"], led["reason"]
        S = copy.deepcopy(saved)
        S["multi"]["outcome_priority"] = ["refused", "dispute"]
        led2, _ = run(script, prods=P2)
        assert ("p1", S["events"]["dispute"]["note"]) in led2["notes"] or led2["notes"]
        assert (led2["outcome"], led2["reason"]) == (S["events"]["refused"]["outcome"], S["events"]["refused"]["reason"])
        assert first == (S["events"]["dispute"]["outcome"], S["events"]["dispute"]["reason"])   # account order without it
    finally:
        S = saved


def test_notes_before_a_direct_transfer_only_when_the_brief_says_so():
    global S
    saved = S
    try:
        S = copy.deepcopy(saved)
        S["rules"]["hardship_transfer"] = "direct"
        S["events"]["transfer_support"]["queue"] = S["events"]["transfer_support"].get("queue") or "support"
        S["events"]["hardship"]["note"] = S["events"]["hardship"].get("note") or "hardship"
        led, _ = run([{"k": "hardship"}])
        assert led["notes"] == [] and led["transfers"]
        S["rules"]["notes_before_transfer"] = True
        led, _ = run([{"k": "hardship"}])
        n = S["events"]["hardship"]["note"]
        assert led["notes"] == [("p1", n), ("p2", n)] and led["calls"][-2:] == ["transfer_to_agent", "close_call"]
    finally:
        S = saved


def test_note_codes_and_floor_rounding_per_product_type():
    from builder import spec_model, extract
    from builder.runtime import engine
    global S
    saved = S
    try:
        S = copy.deepcopy(saved)
        S["events"]["refused"]["note"] = {"credit_card": "NC-REF", "personal_loan": "NL-REF"}
        assert not [e for e in spec_model.check(S) if "note" in e]
        led, _ = run([{"k": "no"}] * 8)
        assert sorted(led["notes"]) == [("p1", "NC-REF"), ("p2", "NL-REF")]
        S["products"]["floor_field"] = {}
        S["products"]["floor_pct"] = 15
        S["products"]["floor_round"] = {"credit_card": "up:5", "personal_loan": "up:10"}
        assert not [e for e in spec_model.check(S) if "floor_round" in e]
        engine.S = S
        f = lambda typ, amt: engine.product_facts({"now": "2026-10-14T11:00"}, {"product_id": "x", "type": typ, "past_due": amt, "days_late": 5})["floor"]
        assert (f("credit_card", 437.8), f("personal_loan", 612.35)) == (70.0, 100.0)
        S["products"]["floor_round"] = {"credit_card": "up_five"}
        assert [e for e in spec_model.check(S) if "floor_round" in e]
    finally:
        S = saved


def test_an_engine_crash_during_negotiation_is_a_service_error_not_a_refusal():
    from builder.runtime import engine, cal
    s = copy.deepcopy(S)
    engine.S = s
    cal.P = dict(workdays=s["calendar"]["workdays"], holidays=s["calendar"]["holidays"])
    saved = engine.run
    engine.run = lambda V: 1 / 0
    try:
        V = {"now": "2026-10-14T11:00", "_state": json.dumps(
            {"stage": "nego", "ci": 0, "products": [{"id": "p1", "type": "credit_card", "status": "open"}]})}
        engine.main(V)
        assert json.loads(V["_state"])["products"][0]["status"] == "service_error"
        V = {"now": "2026-10-14T11:00", "_state": json.dumps({"stage": "id", "qi": 0})}
        engine.main(V)
        assert (V["c_outcome"], V["c_reason"]) == (s["events"]["service_error"]["outcome"], s["events"]["service_error"]["reason"] or "")
    finally:
        engine.run = saved


def test_a_rule_for_one_product_type_does_not_apply_to_the_other_types():
    from builder.runtime import engine
    global S
    saved = S
    try:
        S = copy.deepcopy(saved)
        S["events"]["refused"]["note"] = {"credit_card": "CARD_REFUSED"}
        led, _ = run([{"k": "no"}] * 8)
        assert sorted(led["notes"]) == [("p1", "CARD_REFUSED")]                  # the loan gets no note
        S["products"].update(floor_field={}, floor_pct=15, floor_full_below={"credit_card": 400}, floor_round="up_unit")
        engine.S = S
        f = lambda typ: engine.product_facts({"now": "2026-10-14T11:00"}, {"product_id": "x", "type": typ, "past_due": 312.34, "days_late": 5})["floor"]
        assert (f("credit_card"), f("personal_loan")) == (312.34, 47.0)
    finally:
        S = saved


def test_never_zero_drops_an_inexpressible_optional_value_and_flags_it():
    from builder import build, spec_model
    raw = json.load(open(ROOT / "submission" / "brief-b.spec.json"))
    raw["products"]["step_round"] = {"credit_card": "up:5"}                  # not a form step_round accepts
    raw["events"]["refused"]["note"] = 7                                     # wrong type in an optional field
    assert spec_model.check(build.finalize(copy.deepcopy(raw), O))
    fixed, dropped = build.degrade(raw, O)
    assert not spec_model.check(build.finalize(copy.deepcopy(fixed), O)) and len(dropped) == 2
    assert all(any(d[:20] in u for u in fixed["unsupported_rules"]) for d in dropped)   # INCOMPLETE, never silent
    broken = json.load(open(ROOT / "submission" / "brief-b.spec.json"))
    broken["bands"] = "early"                                                # a required part: not dropped
    assert build.degrade(broken, O)[1] == []
