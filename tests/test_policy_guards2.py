"""Rules found by the robustness round (eval/robust): each one comes from the brief, none is a fixed policy."""
import copy
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "eval"))
import test_engine_edge as E  # noqa: E402
from builder import compile as comp, spec_model  # noqa: E402
from builder.runtime import cal, engine  # noqa: E402

O = json.load(open(ROOT / "kit" / "build-the-builder" / "tools" / "openapi.json"))


def eval_score():
    import importlib.util
    spec_ = importlib.util.spec_from_file_location("eval_score", ROOT / "eval" / "score.py")
    m = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(m)
    return m


def facts(spec, rec, now="2026-11-24T10:00"):
    s = comp.apply_defaults(copy.deepcopy(spec), O)
    engine.S = s
    cal.P = dict(workdays=s["calendar"]["workdays"], holidays=s["calendar"]["holidays"])
    return engine.product_facts(dict(now=now), dict(rec, product_id="p1"))


def test_rounding_steps():
    r = engine.round_rule
    assert (r(24.675, "up:0.05"), r(25.05, "up:0.05"), r(24.671, "down:0.05"), r(24.675, "nearest:0.05")) == (24.7, 25.05, 24.65, 24.7)
    assert (r(100.002, "up_unit"), r(90.00000000000001, "up_unit"), r(12.349, None)) == (101.0, 90.0, 12.35)


def test_floor_percentage_per_type_step_rounding_and_minimum():
    spec = copy.deepcopy(E.A)
    spec["products"].update(floor_field={}, floor_pct={"credit_card": 10, "personal_loan": 25}, floor_round="up:0.05", floor_min=20)
    assert facts(spec, dict(type="credit_card", days_late=12, past_due=246.71))["floor"] == 24.7    # 24.671 -> 24.70
    assert facts(spec, dict(type="credit_card", days_late=12, past_due=98.7))["floor"] == 20.0      # 9.87 -> minimum 20
    assert facts(spec, dict(type="credit_card", days_late=12, past_due=15.4))["floor"] == 15.4      # debt below the minimum
    assert facts(spec, dict(type="personal_loan", days_late=12, past_due=100.2))["floor"] == 25.05
    assert spec_model.check(comp.apply_defaults(copy.deepcopy(spec), O)) == []


def test_a_band_can_make_the_whole_debt_the_floor():
    spec = copy.deepcopy(E.A)
    ff = spec["products"]["floor_field"]["credit_card"]
    late = max(spec["bands"], key=lambda b: b["min"])
    late["floor"] = "full"
    rec = {"type": "credit_card", "past_due": 300.0, ff: 50.0}
    assert facts(spec, dict(rec, days_late=late["min"]))["floor"] == 300.0
    assert facts(spec, dict(rec, days_late=1))["floor"] == 50.0


def offers(spec, now, rec):
    score = eval_score()
    s = comp.apply_defaults(copy.deepcopy(spec), O)
    engine.S = s
    cal.P = dict(workdays=s["calendar"]["workdays"], holidays=s["calendar"]["holidays"])
    return score.offers(s, now, rec)


def test_a_skipped_repeat_counts_only_when_the_brief_says_so():
    spec = copy.deepcopy(E.A)
    spec["rules"].pop("week_end_today", None)
    spec["ladder"] = [dict(amount="full", date="today"), dict(amount="full", date="deadline"), dict(amount="floor", date="deadline")]
    b = min(spec["bands"], key=lambda b: b["min"])
    b["attempts"], b["ladder"] = 2, None
    rec = {"product_id": "p1", "type": "credit_card", "past_due": 300.0, "days_late": b["min"],
           spec["products"]["floor_field"]["credit_card"]: 90.0}
    spec["rules"]["opening_blocks_repeat"] = True                         # r2: "the opening included"
    # step 1 (full today) repeats the opening ask: skipped
    spec["rules"]["skipped_repeat_counts"] = True
    assert len(offers(spec, "2026-10-14T11:00", rec)) == 1
    spec["rules"]["skipped_repeat_counts"] = False
    assert len(offers(spec, "2026-10-14T11:00", rec)) == 2
    spec["rules"].pop("skipped_repeat_counts")
    assert len(offers(spec, "2026-10-14T11:00", rec)) == 1                  # the default, reported as an assumption
    assert spec_model.assumed(comp.apply_defaults(copy.deepcopy(spec), O))


def test_a_step_equal_to_the_opening_ask_follows_the_brief():
    spec = copy.deepcopy(E.A)
    spec["ladder"] = [dict(amount="full", date="today"), dict(amount="floor", date="deadline")]
    b = min(spec["bands"], key=lambda b: b["min"])
    b["attempts"], b["ladder"] = 2, None
    rec = {"product_id": "p1", "type": "credit_card", "past_due": 300.0, "days_late": b["min"],
           spec["products"]["floor_field"]["credit_card"]: 90.0}
    spec["rules"]["opening_blocks_repeat"] = True              # r2: a step equal to the opening ask is a repeat
    assert [300.0, "2026-10-14"] not in offers(spec, "2026-10-14T11:00", rec)
    spec["rules"]["opening_blocks_repeat"] = False             # p1: the opening ask "is not a proposal"
    assert offers(spec, "2026-10-14T11:00", rec)[0] == [300.0, "2026-10-14"]


def test_returning_to_a_product_repeats_its_open_offer():
    score = eval_score()
    spec = copy.deepcopy(E.B)
    s = score.setup(spec, O)
    score.OPENAPI[0] = O
    prods = [{"product_id": "p1", "type": "credit_card", "past_due": 300.0, "days_late": 5, "min_payment": 90.0},
             {"product_id": "p2", "type": "personal_loan", "past_due": 500.0, "days_late": 5, "min_payment": 100.0}]
    first = score.conversation(s, {"now": "2026-10-14T11:00", "products": prods, "script": [{"k": "no"}]}, O)
    got = score.conversation(s, {"now": "2026-10-14T11:00", "products": prods, "script": [
        {"k": "no"}, {"k": "proposes", "date": "2026-10-16", "amount": 500.0, "product": "personal_loan"},
        {"k": "yes"}, {"k": "yes"}]}, O)
    card = [p for p in got["promises"] if p[0] == "p1"]
    assert card and card[0][1] == 300.0, got                                  # the card's own offer, not its floor


def test_a_tool_the_api_does_not_offer_does_not_crash_the_build():
    o = copy.deepcopy(O)
    o["paths"].pop("/schedule_callback")
    s = comp.apply_defaults(copy.deepcopy(E.A), o)
    assert s["callback"]["days"] == []
    comp.compile_workflow(s, o)


def test_a_missing_tool_needs_no_body_mapping():
    from builder import extract
    o = copy.deepcopy(O)
    o["paths"].pop("/schedule_callback")
    s = copy.deepcopy(E.A)
    s["tool_bodies"]["schedule_callback"] = {}
    assert not [e for e in extract.validate(s, o) if "schedule_callback" in e]


def test_progress_needs_fixes_without_losses_or_moved_rules():
    from builder import extract
    old = copy.deepcopy(E.A)
    old["products"]["floor_min"] = 20
    dropped = copy.deepcopy(old)
    dropped["products"].pop("floor_min")                      # "fixes" an error by deleting a stated value
    assert not extract.progress(old, dropped, ["e1"], [])[0]
    moved = copy.deepcopy(old)
    moved["unsupported_rules"] = ["the floor is never below 20"]   # "fixes" it by declaring the rule not carried
    assert not extract.progress(old, moved, ["e1"], [])[0]
    worse = copy.deepcopy(old)
    assert not extract.progress(old, worse, ["e1"], ["e2"])[0]      # trades one problem for another
    fixed = copy.deepcopy(old)
    fixed["products"]["floor_min"] = 25
    assert extract.progress(old, fixed, ["e1"], [])[0]              # a changed value is fine


def test_a_rule_not_carried_makes_the_build_incomplete():
    import pytest
    from builder import build
    from builder.trace import Trace
    t = Trace(str(ROOT / "traces" / "test-verdict.trace.log"))
    spec = comp.apply_defaults(copy.deepcopy(E.A), O)
    spec["unsupported_rules"] = ["round the floor up to the next 0.05"]
    with pytest.raises(SystemExit) as e:
        build.finish(t, spec, {"failed": []})
    assert e.value.code == 3
    t = Trace(str(ROOT / "traces" / "test-verdict.trace.log"))
    spec["unsupported_rules"] = []
    build.finish(t, spec, {"failed": []})                           # complete: no exit
    assert "RESULT: COMPLETE" in open(ROOT / "traces" / "test-verdict.trace.log").read()


def test_promise_retries_come_from_the_brief():
    score = eval_score()
    spec = copy.deepcopy(E.B)
    prods = [{"product_id": "p1", "type": "credit_card", "past_due": 300.0, "days_late": 5, "min_payment": 90.0}]
    script = [{"k": "yes"}, {"k": "yes"}]
    for retries, recorded in ((None, True), (1, True), (0, False)):
        spec["rules"]["promise_retries"] = retries
        s = score.setup(spec, O)
        score.OPENAPI[0] = O
        got = score.conversation(s, {"now": "2026-10-14T11:00", "products": prods, "script": script,
                                     "faults": {"create_promise": 1}}, O)
        assert bool(got["promises"]) == recorded, (retries, got)


def test_a_customer_reference_under_another_name_reaches_every_node():
    o = json.load(open(ROOT / "eval" / "robust" / "r3" / "openapi.json"))
    s = json.load(open(ROOT / "eval" / "robust" / "results" / "r3-B-3a2c263509.spec.json"))
    from builder import extract
    assert not [e for e in extract.validate(copy.deepcopy(s), o) if "'customer_id' is not a slot" in e]
    wf = comp.compile_workflow(comp.apply_defaults(s, o), o)
    for n in ("api_promise", "api_promise_2", "api_promise_3", "api_note_2", "api_close"):
        if n in wf["nodes"]:
            b = wf["nodes"][n]["pre_actions"][0]["function"]["parameters"]["properties"]["body"]["properties"]
            assert b["client_ref"]["default"] == "{{customer_id}}", (n, b["client_ref"])


def test_dated_event_changes_apply_from_their_date(monkeypatch):
    spec = comp.apply_defaults(copy.deepcopy(E.A), O)
    paid = spec["events"]["paid"]["outcome"]
    spec["event_changes"] = [{"event": "paid", "from": "2026-11-02", "set": {"outcome": "claims_paid"}}]
    monkeypatch.setattr(engine, "S", spec)
    monkeypatch.setattr(engine, "TODAY", [__import__("datetime").date(2026, 11, 1)])
    assert engine.ev("paid")["outcome"] == paid
    engine.TODAY[0] = __import__("datetime").date(2026, 11, 2)
    assert engine.ev("paid")["outcome"] == "claims_paid"
    from builder import extract
    assert any("event_changes" in e for e in extract.validate({**spec, "event_changes": [{"event": "nope", "from": "x", "set": {}}]}, O))


def test_hardship_can_transfer_without_a_question():
    from sim import run_case
    spec = copy.deepcopy(E.A)
    spec["rules"]["hardship_transfer"] = "direct"
    led, tr = run_case(spec, E.CASES["PUB-01"], E.ids("PUB-01") + [dict(k="hardship")])
    assert [t["queue"] for t in led["transfers"]] == [spec["events"]["transfer_support"]["queue"]], E.agent_lines(tr)
    spec["rules"].pop("hardship_transfer")
    led, tr = run_case(spec, E.CASES["PUB-01"], E.ids("PUB-01") + [dict(k="hardship")])
    assert led["transfers"] == [], E.agent_lines(tr)        # the default: the support transfer is offered first


def test_roll_when_earlier_than_today_differs_from_roll_when_today():
    spec = copy.deepcopy(E.A)
    spec["calendar"]["holidays"] = []
    b = spec["bands"][0]
    b.update(min=1, max=30)
    spec["bands"] = [b]
    rec = dict(type="credit_card", days_late=5, past_due=100.0)
    b["deadline"] = {"kind": "last_business_day_of_month", "roll_if_before_today": True}
    assert facts(spec, rec, "2026-11-30T10:00")["deadline"] == "2026-11-30"     # today is that day: stays
    b["deadline"] = {"kind": "last_business_day_of_month", "roll_if_not_after_today": True}
    assert facts(spec, rec, "2026-11-30T10:00")["deadline"] == "2026-12-31"     # today is that day: rolls


def test_policy_values_name_a_sentence_that_is_really_in_the_materials():
    from builder import extract
    docs = "27. Never propose the same amount on the same date twice. If an attempt would repeat an earlier proposal " \
           "exactly, skip it: it is not a proposal and the customer is not asked again."
    spec = {"rules": {"skipped_repeat_counts": False, "ladder_repeat_last": False}, "products": {}, "identity": {},
            "sources": {"rules.skipped_repeat_counts": "If an attempt would repeat an earlier proposal exactly, skip it: "
                                                       "it is not a proposal"}}
    bad, missing = extract.provenance(spec, docs)
    assert bad == [] and missing == []                       # false values are values too: ladder_repeat_last is unset
    spec["rules"]["promise_retries"] = 0
    spec["sources"]["rules.promise_retries"] = "A failed promise is never retried."      # not in the materials
    bad, missing = extract.provenance(spec, docs)
    assert len(bad) == 1 and "promise_retries" in bad[0]
    spec["rules"]["week_end_today"] = "today"
    assert "rules.week_end_today" in extract.provenance(spec, docs)[1]


def test_too_much_skips_later_full_steps_only_when_the_brief_says_so():
    import builder.runtime.engine as eng
    spec = copy.deepcopy(E.A)
    spec["rules"].pop("week_end_today", None)
    spec["ladder"] = [dict(amount="floor", date="deadline"), dict(amount="full", date="deadline")]
    s = comp.apply_defaults(copy.deepcopy(spec), O)
    eng.S = s
    cal.P = dict(workdays=s["calendar"]["workdays"], holidays=s["calendar"]["holidays"])
    p = dict(full=300.0, floor=90.0, too_much=True, floor_offered=True, refused_offers=[], used=1, made=1, attempts=3,
             deadline="2026-10-20", ladder=s["ladder"], status="open", name="card", offer=None, type="credit_card")
    calls = []
    saved = eng.say, eng.talk, eng.advance, eng.focus
    eng.say = lambda *a: None; eng.talk = lambda *a: None; eng.focus = lambda *a: None
    eng.advance = lambda V_, s_, pre="": calls.append("advance")
    try:
        V = {"now": "2026-10-14T11:00"}
        s["rules"]["too_much_skips_full"] = True                    # r2 rule 19
        eng.make_offer(V, {"products": [p]}, p, 2)
        assert p["offer"] is None and p["status"] == "refused"
        p.update(status="open", offer=None); s["rules"].pop("too_much_skips_full")
        eng.make_offer(V, {"products": [p]}, p, 2)
        assert p["offer"] == [300.0, "2026-10-20"]                  # brief silent: the step is offered
    finally:
        eng.say, eng.talk, eng.advance, eng.focus = saved
