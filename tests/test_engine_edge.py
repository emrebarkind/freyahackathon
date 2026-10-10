"""Edge cases found by the audit, run on the engine with the gold Brief A spec and public-case data."""
import copy
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "kit" / "build-the-builder" / "tools"))
os.environ.setdefault("FREYA_BANK_TEAM_KEY", "local-test-key-0000")
from sim import run_case  # noqa: E402

CASES = {c["id"]: c for c in json.load(open(ROOT / "kit" / "build-the-builder" / "public-test-set.json"))}
A = json.load(open(ROOT / "specs" / "brief-a.gold.json"))
C = dict(k="confirmed", t="yes, speaking")


def ids(cid):
    c = CASES[cid]
    return [C, dict(k="answer", t=c["identity"]["date_of_birth"]), dict(k="answer", t=c["identity"]["phone_last4"])]


def agent_lines(tr):
    return [t for w, t in tr if w == "agent"]


def test_vague_then_no_exact_day_proposes_deadline():
    # PUB-07 data: early band, deadline Mon 2 Nov (26 Oct is a holiday)
    script = ids("PUB-07") + [dict(k="vague", d="when my salary comes", t="when my salary comes"),
                              dict(k="unclear", t="I don't know exactly"), dict(k="yes"), dict(k="yes")]
    led, tr = run_case(A, CASES["PUB-07"], script)
    assert [(p["product_id"], p["date"]) for p in led["promises"]] == [("p1", "2026-11-02")], agent_lines(tr)


def test_callback_day_then_time():
    script = [dict(k="third_party", t="this is her husband"), dict(k="gives_time", t="tomorrow"), dict(k="gives_time", t="around eleven")]
    led, tr = run_case(A, CASES["PUB-02"], script)
    assert led["callbacks"] == [dict(date="2026-10-15", time="11:00")], agent_lines(tr)
    assert (led["outcome"], led["reason"]) == ("not_reached", "callback")


def test_callback_time_only_means_today():
    script = [dict(k="third_party", t="her brother here"), dict(k="gives_time", t="she'll be home after 5")]
    led, tr = run_case(A, CASES["PUB-02"], script)
    assert led["callbacks"] == [dict(date="2026-10-14", time="17:00")], agent_lines(tr)


def test_change_request_after_recorded_promise():
    script = ids("PUB-01") + [dict(k="yes"), dict(k="yes"), dict(k="change", t="can I move it to Friday?")]
    led, tr = run_case(A, CASES["PUB-01"], script)
    assert len(led["promises"]) == 1 and led["outcome"] == "promise"


def test_restructuring_after_recorded_promise_closes_transferred():
    script = ids("PUB-01") + [dict(k="yes"), dict(k="yes"), dict(k="restructure", t="actually I want lower instalments in future")]
    led, tr = run_case(A, CASES["PUB-01"], script)
    assert (led["outcome"], led["reason"]) == ("transferred", "restructuring") and len(led["promises"]) == 1


def test_human_insists_after_offer_to_help():
    script = ids("PUB-01") + [dict(k="human", t="I want a real person"), dict(k="no", t="no, just put me through")]
    led, tr = run_case(A, CASES["PUB-01"], script)
    assert led["transfers"] == [dict(queue="general")] and (led["outcome"], led["reason"]) == ("transferred", "human")


def test_yes_but_other_date_at_readback():
    script = ids("PUB-10") + [dict(k="no"), dict(k="yes"), dict(k="yes", d="Monday the 19th", t="yes, oh wait, make it Monday the 19th"), dict(k="yes")]
    case = copy.deepcopy(CASES["PUB-10"])
    case.pop("faults", None)
    led, tr = run_case(A, case, script)
    assert [(p["date"]) for p in led["promises"]] == ["2026-10-19"], agent_lines(tr)


def test_too_much_with_amount():
    script = ids("PUB-01") + [dict(k="too_much", a=300, t="that's too much, I could manage three hundred"), dict(k="proposes", d="Friday"), dict(k="yes")]
    led, tr = run_case(A, CASES["PUB-01"], script)
    assert [(p["amount"], p["date"]) for p in led["promises"]] == [(300.0, "2026-10-16")], agent_lines(tr)


def test_hardship_counter_proposal_not_recordable_ends_as_hardship():
    script = ids("PUB-05") + [dict(k="hardship"), dict(k="proposes", a=50, d="Friday", t="no transfer, but I could pay fifty on Friday"), dict(k="no")]
    led, tr = run_case(A, CASES["PUB-05"], script)
    assert (led["outcome"], led["reason"]) == ("no_promise", "hardship") and not led["promises"], agent_lines(tr)


def test_robot_side_question_at_opening_is_answered():
    script = [dict(k="unclear", side="robot", t="hello? wait, is this a robot?"), C] + ids("PUB-08")[1:] + [dict(k="already_paid")]
    led, tr = run_case(A, CASES["PUB-08"], script)
    assert "digital assistant" in agent_lines(tr)[1] and led["outcome"] == "paid"


def test_relative_reveals_during_identity_goes_to_callback_flow():
    script = [C, dict(k="wrong_person", t="oh, you want Maria? I'm her husband"), dict(k="gives_time", t="tomorrow at eleven")]
    led, tr = run_case(A, CASES["PUB-02"], script)
    assert (led["outcome"], led["reason"]) == ("not_reached", "callback")
