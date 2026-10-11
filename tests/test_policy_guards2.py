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
    # step 1 (full today) repeats the opening ask: skipped
    spec["rules"]["skipped_repeat_counts"] = True
    assert len(offers(spec, "2026-10-14T11:00", rec)) == 1
    spec["rules"]["skipped_repeat_counts"] = False
    assert len(offers(spec, "2026-10-14T11:00", rec)) == 2
    spec["rules"].pop("skipped_repeat_counts")
    assert len(offers(spec, "2026-10-14T11:00", rec)) == 1                  # the default, reported as an assumption
    assert spec_model.assumed(comp.apply_defaults(copy.deepcopy(spec), O))


def test_the_opening_ask_is_never_proposed_again_as_a_step():
    spec = copy.deepcopy(E.A)
    spec["ladder"] = [dict(amount="full", date="today"), dict(amount="floor", date="deadline")]
    b = min(spec["bands"], key=lambda b: b["min"])
    b["attempts"], b["ladder"] = 2, None
    rec = {"product_id": "p1", "type": "credit_card", "past_due": 300.0, "days_late": b["min"],
           spec["products"]["floor_field"]["credit_card"]: 90.0}
    assert [300.0, "2026-10-14"] not in offers(spec, "2026-10-14T11:00", rec)


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
