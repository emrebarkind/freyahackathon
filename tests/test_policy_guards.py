"""Policies that differ between briefs must come from the brief, never from brief A by default.
1. "Last business day of this week" when today is that day: next week only if the brief says so.
2. A ladder step that would repeat an earlier proposal is skipped; whether it uses an attempt is the brief's call."""
import copy
import datetime
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import test_engine_edge as E  # noqa: E402
from builder import compile as comp, spec_model  # noqa: E402
from builder.runtime import cal, engine  # noqa: E402
from sim import run_case  # noqa: E402

FRI = datetime.date(2026, 10, 16)
O = E.json.load(open(ROOT / "kit" / "build-the-builder" / "tools" / "openapi.json"))


def test_week_end_rollover_only_when_the_brief_states_it(monkeypatch):
    monkeypatch.setattr(cal, "P", dict(workdays=[0, 1, 2, 3, 4], holidays=[]))
    monkeypatch.setattr(engine, "S", {"rules": {"week_end_today": "next_week"}})
    assert engine.ladder_date(FRI, "last_business_day_this_week", None) == datetime.date(2026, 10, 23)
    monkeypatch.setattr(engine, "S", {"rules": {}})
    assert engine.ladder_date(FRI, "last_business_day_this_week", None) == FRI
    assert engine.ladder_date(FRI - datetime.timedelta(days=2), "last_business_day_this_week", None) == FRI


def test_an_unstated_week_end_rule_is_reported():
    spec = comp.apply_defaults(copy.deepcopy(E.A), O)
    assert not [u for u in spec_model.unsupported(spec) if "this week" in u]       # brief A states it
    spec["rules"].pop("week_end_today")
    assert [u for u in spec_model.unsupported(spec) if "this week" in u]


def offers_on_friday(spec, attempts):
    spec["bands"][0]["attempts"] = attempts
    case = copy.deepcopy(E.CASES["PUB-01"])
    case["variables"]["now"] = "2026-10-16T11:00"
    case["products"][0]["days_late"] = 5
    led, tr = run_case(spec, case, E.ids("PUB-01") + [dict(k="no")] * 4)
    return [l for l in E.agent_lines(tr) if "Could you pay" in l]


def test_a_skipped_repeat_uses_no_attempt():
    spec = copy.deepcopy(E.A)
    spec["rules"] = dict(spec["rules"], opening_is_attempt=True, skipped_repeat_counts=False)   # q1's own rule
    spec["rules"].pop("week_end_today", None)                 # the step is read literally: today
    spec["ladder"] = [dict(amount="full", date="today"), dict(amount="full", date="last_business_day_this_week"),
                      dict(amount="full", date="deadline")]
    spec["bands"][0]["ladder"] = None
    lines = offers_on_friday(spec, attempts=2)                 # opening + one more proposal
    assert len(lines) == 1 and "Friday 16 October" not in lines[0], lines   # step 2 = today = the opening: skipped


def test_no_window_on_any_weekday_is_no_callback():
    s = copy.deepcopy(E.A)
    s["callback"]["windows"] = {str(i): None for i in range(7)}
    spec_model.normalise(s)
    assert s["callback"]["days"] == [] and "windows" not in s["callback"]
    s = copy.deepcopy(E.A)
    s["callback"]["windows"] = {"5": None}                     # one day closed: a real per-day policy, kept
    spec_model.normalise(s)
    assert s["callback"]["windows"] == {"5": None} and s["callback"]["days"]
