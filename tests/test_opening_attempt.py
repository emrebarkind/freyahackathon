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
