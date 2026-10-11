"""Customer sentences that broke candidate 8 (found 11 Oct through the real extraction path and an engine probe),
with the normal answers and real corrections that must keep working. Extraction values are the platform's where it
was observed (chat probes 680c4bd7 and 034c98c0)."""
import copy, json, pathlib
from builder import selftest

ROOT = pathlib.Path(__file__).resolve().parent.parent
OA = json.load(open(ROOT / "kit" / "build-the-builder" / "tools" / "openapi.json"))
CASES = {c["id"]: c for c in json.load(open(ROOT / "kit" / "build-the-builder" / "public-test-set.json"))}
SA = json.load(open(ROOT / "eval" / "clean-runs" / "cand8-a" / "cand8-a.spec.json"))


def T(k, t, d="", a="", cut="no"):
    return dict(k=k, t=t, d=d, a=a, f="none", side="none", cut=cut)


YES = T("yes", "Yes, I confirm.")


def run(cid, turns, na=None):
    s = copy.deepcopy(SA)
    if na is not None:
        s["rules"]["non_answer_counts"] = na
    c = CASES[cid]
    prods = [dict(p, product_id=f"p{i + 1}") for i, p in enumerate(c["products"])]
    bank = selftest.GenericBank(copy.deepcopy(s), c["identity"], prods)
    i = c["identity"]
    head = [T("confirmed", "Yes, that's me."), dict(k="answer", t=i["date_of_birth"], norm=i["date_of_birth"]),
            dict(k="answer", t=str(i["phone_last4"]), norm=str(i["phone_last4"]))]
    led, tr = selftest.simulate(s, dict(customer_id="c", **c["variables"]), bank, head + turns, openapi=OA, max_steps=4000)
    return led, [x[1] for x in tr if x[0] == "agent"]


# ---- 1. amounts in two pieces (PUB-06: card 2125.10 past due, floor 637.50; now Wed 14 Oct, Friday = 16 Oct)
def test_amount_hundreds_and_then_the_rest_is_one_number():
    led, _ = run("PUB-01", [T("proposes", "I can pay three hundred and", cut="yes"), T("proposes", "fifty dollars on Friday.", d="Friday", a=50.0), YES])
    assert led["promises"] == [("p1", 350.0, "2026-10-16")]


def test_amount_number_then_two_digits_is_clarified_not_guessed():
    led, said = run("PUB-06", [T("proposes", "I can pay 700...", a=700.0, cut="yes"), T("proposes", "50 on Friday.", d="Friday", a=50.0)])
    assert led["promises"] == [] and "create_promise" not in led["calls"]
    assert "amount right" in said[-1]                               # asked, neither 50 nor 700 taken on its own
    led, said = run("PUB-06", [T("proposes", "I can pay 700...", a=700.0, cut="yes"), T("proposes", "50 on Friday.", d="Friday", a=50.0),
                               T("proposes", "Seven hundred dollars and fifty cents, on Friday.", d="Friday", a=700.5), YES])
    assert led["promises"] == [("p1", 700.5, "2026-10-16")]


def test_amount_correction_after_a_cut_piece_takes_the_new_value():
    led, said = run("PUB-06", [T("proposes", "I can pay 700...", a=700.0, cut="yes"), T("proposes", "No, sorry, 800 on Friday.", d="Friday", a=800.0), YES])
    assert led["promises"] == [("p1", 800.0, "2026-10-16")] and not any("amount right" in x for x in said)


def test_a_whole_amount_in_one_message_is_not_questioned():
    led, said = run("PUB-06", [T("proposes", "I can pay 700 on Friday.", d="Friday", a=700.0), YES])
    assert led["promises"] == [("p1", 700.0, "2026-10-16")] and not any("amount right" in x for x in said)


def test_identity_digits_in_two_pieces_are_still_joined():
    c = CASES["PUB-01"]
    prods = [dict(p, product_id=f"p{i + 1}") for i, p in enumerate(c["products"])]
    bank = selftest.GenericBank(copy.deepcopy(SA), c["identity"], prods)
    turns = [T("confirmed", "yes"), dict(k="answer", t="14 March 1988", norm="1988-03-14"),
             dict(k="answer", t="44...", norm="44", cut="yes"), dict(k="answer", t="71", norm="71"), T("pay_today", "I can pay it all today."), YES]
    led, _ = selftest.simulate(SA, dict(customer_id="c", **c["variables"]), bank, turns, openapi=OA, max_steps=3000)
    assert led["calls"][:3] == ["verify_identity", "verify_identity", "get_account"] and led["promises"] == [("p1", 420.0, "2026-10-14")]


# ---- 2. an explicit "no" to a day
def test_a_rejected_day_is_not_read_back_and_a_plain_yes_does_not_accept_it():
    led, said = run("PUB-01", [T("no", "Yes... no, Friday does not work.", d="Friday"), T("yes", "Yes.")])
    assert led["promises"] == [] and not any("16 October" in x for x in said)
    led, said = run("PUB-01", [T("no", "Yes... no, Friday does not work.", d="Friday"), T("yes", "Yes."),
                               T("proposes", "I can pay the full amount on the 20th.", d="the 20th"), YES])
    assert led["promises"] == [("p1", 420.0, "2026-10-20")] and not any("16 October" in x for x in said)


def test_a_real_correction_inside_one_message_keeps_working():
    led, _ = run("PUB-01", [T("proposes", "The 21st, sorry, I mean the 20th.", d="the 20th"), YES])
    assert led["promises"] == [("p1", 420.0, "2026-10-20")]


# ---- 3. questions back and non-progress
def test_the_same_question_asked_again_is_not_a_refusal():
    led, said = run("PUB-01", [T("question", "Why is it so much?")] * 4, na=False)
    assert led["notes"] == [] and "close_call" not in led["calls"]
    assert not any(x.startswith("Could you pay") for x in said)     # no persuasion attempt was used


def test_questions_alternating_with_fragments_stay_bounded_only_by_the_briefs_rule():
    frag = T("unclear", "I was thinking...", cut="yes")
    led, said = run("PUB-01", [T("question", "What?"), frag] * 20, na=True)
    assert led["outcome"] == "no_promise" and led["promises"] == [] and len(said) < 40
    led, said = run("PUB-01", [T("question", "What?"), frag] * 20, na=False)
    assert "close_call" not in led["calls"] and led["notes"] == []   # no outcome code invented
