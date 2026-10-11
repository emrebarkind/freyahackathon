"""rules.opening_is_attempt: when the brief counts the opening 'full amount today' ask as attempt 1, its refusal uses
an attempt. Such a brief's early band (1 attempt) gets no follow-up offer; a band with 2 attempts gets one more."""
import copy
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import test_engine_edge as E  # noqa: E402
from sim import run_case  # noqa: E402


def offers(spec, case_id, days_late=None):
    case = copy.deepcopy(E.CASES[case_id])
    if days_late is not None:
        case["products"][0]["days_late"] = days_late
    script = E.ids(case_id) + [dict(k="no"), dict(k="no"), dict(k="no")]
    led, tr = run_case(spec, case, script)
    return [l for l in E.agent_lines(tr) if "Could you pay" in l], led


def test_opening_refusal_uses_attempt_one_when_the_brief_says_so():
    spec = copy.deepcopy(E.A)
    spec["rules"] = dict(spec.get("rules") or {}, opening_is_attempt=True)
    spec["bands"][0]["attempts"] = 1
    lines, led = offers(spec, "PUB-01", days_late=5)
    assert lines == [], lines                       # the opening ask was the only attempt
    assert led["outcome"] == "no_promise", led


def test_two_attempts_give_one_follow_up_offer():
    spec = copy.deepcopy(E.A)
    spec["rules"] = dict(spec.get("rules") or {}, opening_is_attempt=True)
    spec["bands"][0]["attempts"] = 2
    lines, _ = offers(spec, "PUB-01", days_late=5)
    assert len(lines) == 1, lines


def test_without_the_rule_the_opening_is_not_counted():
    spec = copy.deepcopy(E.A)
    spec["bands"][0]["attempts"] = 1
    lines, _ = offers(spec, "PUB-01", days_late=5)
    assert len(lines) == 1, lines


def test_eight_digit_birth_dates_in_the_briefs_order(monkeypatch):
    from builder.runtime import engine
    monkeypatch.setattr(engine, "S", {"identity": {"date_order": "dmy"}})   # restored after the test
    assert engine.normalize_answer({"kind": "date"}, "21061985") == "1985-06-21"
    assert engine.normalize_answer({"kind": "date"}, "2 1 0 6 1 9 8 5") == "1985-06-21"
    assert engine.normalize_answer({"kind": "date"}, "31021985") == ""          # 31 February: not a date
    assert engine.normalize_answer({"kind": "date"}, "1988-03-14") == "1988-03-14"   # written dates are not digit strings
    monkeypatch.setattr(engine, "S", {"identity": {"date_order": "mdy"}})
    assert engine.normalize_answer({"kind": "date"}, "06211985") == "1985-06-21"



def test_digit_order_comes_from_the_brief_never_assumed(monkeypatch):
    from builder.runtime import engine
    monkeypatch.setattr(engine, "S", {"identity": {}})                       # the brief states no order
    assert engine.normalize_answer({"kind": "date"}, "21061985") == ""      # asked again, not guessed
    assert engine.normalize_answer({"kind": "date", "format": "%Y%m%d"}, "19850621") == "1985-06-21"
    assert engine.normalize_answer({"kind": "date", "format": "%m%d%Y"}, "06211985") == "1985-06-21"
    assert engine.normalize_answer({"kind": "date", "format": "%d%m%Y"}, "21061985") == "1985-06-21"
    assert engine.normalize_answer({"kind": "date", "format": "%d/%m/%Y"}, "21061985") == ""   # not a digit-string format
    monkeypatch.setattr(engine, "S", {"identity": {"date_order": "mdy"}})
    assert engine.normalize_answer({"kind": "date"}, "06211985") == "1985-06-21"


def test_a_null_date_order_reads_written_dates(monkeypatch):
    from builder.runtime import engine
    from builder import spec_model
    monkeypatch.setattr(engine, "S", {"identity": {"date_order": None}})
    assert engine.normalize_answer({"kind": "date"}, "7 March 1988") == "1988-03-07"
    assert engine.normalize_answer({"kind": "date"}, "21061985") == ""
    assert not any("date_order" in e for e in spec_model.check(dict(
        __import__("test_engine_edge").A, identity=dict(__import__("test_engine_edge").A["identity"], date_order=None))))
