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


def test_third_party_small_talk_does_not_use_callback_tries():
    script = [dict(k="third_party", t="I am her husband"), dict(k="unclear", t="work has been exhausting today"),
              dict(k="unclear", t="the traffic was a nightmare"), dict(k="gives_time", t="tomorrow morning around eleven")]
    led, tr = run_case(A, CASES["PUB-02"], script)
    assert led["callbacks"] == [dict(date="2026-10-15", time="11:00")], agent_lines(tr)


def test_cut_off_during_identity_does_not_repeat_the_question():
    script = [C, dict(k="answer", t="19 October 1983"), dict(k="answer", t="4401"),
              dict(k="unclear", cut="yes", t="I'm so sorry, I"), dict(k="answer", t="four four one zero"), dict(k="yes"), dict(k="yes")]
    led, tr = run_case(A, CASES["PUB-01"] | dict(identity=dict(date_of_birth="1983-10-19", phone_last4="4410")), script)
    lines = agent_lines(tr)
    assert sum("phone number" in x for x in lines) == 2, lines


def test_clear_yes_in_a_cut_off_message_is_acted_on():
    script = ids("PUB-01") + [dict(k="yes"), dict(k="yes", cut="yes", t="Yes, I confirm. I've been")]
    led, tr = run_case(A, CASES["PUB-01"], script)
    assert len(led["promises"]) == 1, agent_lines(tr)


B = json.load(open(ROOT / "specs" / "brief-b.gold.json"))


def ids_b(cid):
    c = CASES[cid]
    return [C, dict(k="answer", t=c["identity"]["date_of_birth"]), dict(k="answer", t=c["identity"]["phone_last4"])]


def test_multi_restating_agreed_product_does_not_loop():
    # PUB-12 data: the customer repeats "card tomorrow" while the loan offer is on the table
    case = copy.deepcopy(CASES["PUB-12"])
    case["identity"]["phone_last4"] = "4410"
    script = ids_b("PUB-12") + [dict(k="proposes", d="tomorrow", f="credit_card", t="card tomorrow, not the others"),
                                dict(k="proposes", d="tomorrow", f="credit_card", t="I said card tomorrow, I am not paying the loan"),
                                dict(k="no"), dict(k="no"), dict(k="no"), dict(k="yes")]
    led, tr = run_case(B, case, script)
    assert [(p["product_id"], p["date"]) for p in led["promises"]] == [("p1", "2026-10-15")], agent_lines(tr)
    assert sorted((n["product_id"], n["reason"]) for n in led["notes"]) == [("p2", "refused"), ("p3", "refused")]


def test_multi_side_question_at_all_today_keeps_phase():
    script = ids_b("PUB-11") + [dict(k="robot", t="are you a robot?"), dict(k="yes", t="yes, I can pay all of them today"), dict(k="yes")]
    led, tr = run_case(B, CASES["PUB-11"], script)
    assert len(led["promises"]) == 3 and all(p["date"] == "2026-10-14" for p in led["promises"]), agent_lines(tr)


def test_multi_already_paid_all():
    script = ids_b("PUB-11") + [dict(k="already_paid", f="all", t="I paid all of them yesterday")]
    led, tr = run_case(B, CASES["PUB-11"], script)
    assert led["outcome"] == "paid" and sorted(n["reason"] for n in led["notes"]) == ["paid", "paid", "paid"], agent_lines(tr)


def test_multi_weekend_date_for_all_is_adjusted_for_all():
    script = ids_b("PUB-11") + [dict(k="no"), dict(k="proposes", d="Saturday", f="all", t="all of them on Saturday"), dict(k="yes"), dict(k="yes")]
    led, tr = run_case(B, CASES["PUB-11"], script)
    assert sorted(p["date"] for p in led["promises"]) == ["2026-10-19"] * 3, agent_lines(tr)


def test_details_question_is_answered_not_no_info():
    script = ids("PUB-01") + [dict(k="details", t="which card is this about?"), dict(k="yes"), dict(k="yes")]
    led, tr = run_case(A, CASES["PUB-01"], script)
    assert "4821" in agent_lines(tr)[4] and "don't have" not in agent_lines(tr)[4] and len(led["promises"]) == 1



def test_postcode_and_year_identity_from_variant_c():
    spec = json.load(open(ROOT / "submission" / "variant-c.spec.json"))
    import sys as _s
    _s.path.insert(0, str(ROOT))
    from builder import selftest
    bank = selftest.GenericBank(spec, dict(postcode="SW1A1AA", birth_year="1985"),
                                [selftest.make_product(spec, 0, list(spec["products"]["names"])[0], 3)])
    V0 = dict(customer_id="c", first_name="Alex", last_name="Morgan", title="Mr", now="2026-10-14T11:00")
    turns = [dict(k="confirmed"), dict(k="answer", t="it's S W one A, one A A"), dict(k="answer", t="nineteen"),
             dict(k="answer", t="eighty-five"), dict(k="already_paid")]
    led, tr = selftest.simulate(spec, V0, bank, turns)
    assert led["outcome"] == spec["events"]["paid"]["outcome"], tr


# ---------------------------------------------------------------- hidden-brief shapes (audit, hidden lens)
def _gen(spec, turns, products=None, faults=None, identity=None, now="2026-10-14T11:00"):
    import sys as _s
    _s.path.insert(0, str(ROOT))
    from builder import selftest
    ident = identity or {q["field"]: v for q, v in zip(spec["identity"]["questions"], ["1985-06-21", "7777"])}
    prods = products or [selftest.make_product(spec, 0, list(spec["products"]["names"])[0], 3)]
    bank = selftest.GenericBank(spec, ident, copy.deepcopy(prods), faults)
    V0 = dict(customer_id="c", first_name="Alex", last_name="Morgan", title="Mr", now=now)
    return selftest.simulate(spec, V0, bank, turns)


IDS = [dict(k="confirmed"), dict(k="answer", t="21 June 1985"), dict(k="answer", t="7777")]


def test_string_status_success_fields():
    spec = copy.deepcopy(A)
    spec["responses"] = {"create_promise": {"field": "status", "values": ["created"]}}
    spec["identity"]["response"]["pass_values"] = ["pass"]
    led, tr = _gen(spec, IDS + [dict(k="yes"), dict(k="yes")])
    assert len(led["promises"]) == 1 and led["outcome"] == "promise", tr


def test_no_queue_means_no_transfer_and_event_note():
    spec = copy.deepcopy(B)
    spec["events"]["transfer_restructuring"] = dict(outcome="no_promise", reason="plan", queue="", note="plan_requested")
    led, tr = _gen(spec, IDS + [dict(k="restructure")])
    assert led["transfers"] == [] and (led["outcome"], led["reason"]) == ("no_promise", "plan"), tr
    assert led["notes"] == [("p1", "plan_requested")]


def test_hardship_without_support_queue_closes_as_hardship():
    spec = copy.deepcopy(A)
    spec["events"]["transfer_support"]["queue"] = ""
    led, tr = _gen(spec, IDS + [dict(k="hardship")])
    assert led["transfers"] == [] and led["outcome"] == spec["events"]["hardship"]["outcome"], tr


def test_empty_note_code_means_no_note():
    spec = copy.deepcopy(B)
    spec["events"]["refused"]["note"] = ""
    led, tr = _gen(spec, IDS + [dict(k="no")] * 6)
    assert led["notes"] == [] and led["outcome"] == "no_promise", tr


def test_verify_rejections_are_bounded():
    from builder import selftest
    spec = copy.deepcopy(A)

    class Rejecting(selftest.GenericBank):
        def call(self, tool, a):
            if tool == "verify_identity":
                self.led["calls"].append(tool)
                return {"ok": False, "error": "unreadable value"}
            return super().call(tool, a)
    bank = Rejecting(spec, {"date_of_birth": "1985-06-21", "phone_last4": "7777"}, [selftest.make_product(spec, 0, "credit_card", 3)])
    led, tr = selftest.simulate(spec, dict(customer_id="c", first_name="A", last_name="M", title="Mr", now="2026-10-14T11:00"),
                                bank, [dict(k="confirmed")] + [dict(k="answer", t="21 June 1985")] * 6)
    assert led["calls"].count("verify_identity") == 3 and led["outcome"] == spec["events"]["id_failed"]["outcome"], tr


def test_failed_callback_is_not_announced_as_booked():
    led, tr = _gen(A, [dict(k="third_party"), dict(k="gives_time", t="tomorrow at eleven", d="tomorrow")], faults=dict(schedule_callback=2))
    said = " ".join(t for w, t in tr if w == "agent")
    assert led["callbacks"] == [] and "11:00" not in said.split("tomorrow at eleven")[-1] and led["reason"] == "no_callback", tr


def test_identity_date_format_from_spec():
    spec = copy.deepcopy(A)
    spec["identity"]["questions"][0]["format"] = "%d/%m/%Y"
    led, tr = _gen(spec, IDS + [dict(k="yes"), dict(k="yes")], identity={"date_of_birth": "21/06/1985", "phone_last4": "7777"})
    assert len(led["promises"]) == 1, tr


def test_same_type_products_told_apart_by_digits():
    from builder import selftest
    spec = copy.deepcopy(B)
    p1 = selftest.make_product(spec, 0, "credit_card", 3)
    p2 = dict(selftest.make_product(spec, 1, "credit_card", 3), card_last4="1234")
    turns = IDS + [dict(k="proposes", d="Friday", f="credit_card", t="I can pay the card ending one two three four on Friday"),
                   dict(k="no"), dict(k="yes")]
    led, tr = _gen(spec, turns, products=[p1, p2])
    assert [p[0] for p in led["promises"]] == ["p2"], tr


def test_account_without_type_field_and_star_names():
    spec = copy.deepcopy(A)
    spec["products"]["names"] = {"*": "account {label}"}
    spec["products"]["floor_field"] = {"*": "min_due"}
    spec["products"]["floor_names"] = {"*": "minimum due"}
    prod = {"product_id": "A-1", "label": "Platinum", "past_due": 420.0, "days_late": 3, "min_due": 50.0}
    led, tr = _gen(spec, IDS + [dict(k="too_much"), dict(k="yes"), dict(k="yes")], products=[prod])
    said = " ".join(t for w, t in tr if w == "agent")
    assert "None" not in said and "account Platinum" in said and led["promises"][0][1] == 50.0, tr


def test_confirm_waits_through_small_talk():
    led, tr = _gen(A, IDS + [dict(k="yes")] + [dict(k="unclear", t="work has been so busy")] * 3 + [dict(k="yes")])
    assert len(led["promises"]) == 1, tr


def test_verified_customer_callback_when_brief_has_it():
    spec = copy.deepcopy(A)
    spec["events"]["callback_requested"] = dict(outcome="not_reached", reason="callback")
    led, tr = _gen(spec, IDS + [dict(k="call_later", t="can you call me tomorrow?"), dict(k="gives_time", t="tomorrow at eleven", d="tomorrow")])
    assert led["callbacks"] == [("2026-10-15", "11:00")] and led["reason"] == "callback", tr


def test_json_block_takes_the_spec_not_quoted_values():
    import sys as _s
    _s.path.insert(0, str(ROOT))
    from builder.claude import json_block
    t = 'bands: x -- "quote"\n```json\n{"n": 12}\n```\nFinal:\n```json\n{"identity": {}, "events": {}, "lines": {"a": "{name}"}}\n```'
    assert json_block(t, keys=["identity", "events", "lines"]) == {"identity": {}, "events": {}, "lines": {"a": "{name}"}}


# ---------------------------------------------------------------- planned chains (no code run between bank writes)
def _count_steps(fn):
    from builder.runtime import engine
    n = [0]
    orig = engine.main

    def main(V):
        n[0] += 1
        orig(V)
    engine.main = main
    try:
        out = fn()
    finally:
        engine.main = orig
    return out, n[0]


def test_chain_three_promises_then_recorded_turn_in_one_code_run():
    (led, tr), steps = _count_steps(lambda: run_case(B, CASES["PUB-11"], ids_b("PUB-11") + [dict(k="yes"), dict(k="yes")]))
    assert len(led["promises"]) == 3 and led["outcome"] == "promise", agent_lines(tr)
    # open, answer 1, verify result, answer 2 (verify -> account), account, nego, confirm (-> 3 promises + the
    # recorded turn), after (-> close) = 8 code runs; one run per bank write would make it 11
    assert steps <= 8, steps


def test_chain_recovers_when_a_promise_fails_twice():
    import sim
    orig = sim.FakeBank.__call__

    def call(self, tool, body):
        if tool == "create_promise" and body.get("product_id") == "p2":
            self.led["calls"].append(dict(tool=tool, args=body, result="500"))
            return 500, None
        return orig(self, tool, body)
    sim.FakeBank.__call__ = call
    try:
        led, tr = run_case(B, CASES["PUB-11"], ids_b("PUB-11") + [dict(k="yes"), dict(k="yes")])
    finally:
        sim.FakeBank.__call__ = orig
    assert sorted(p["product_id"] for p in led["promises"]) == ["p1", "p3"]
    assert [c["args"]["product_id"] for c in led["calls"] if c["tool"] == "create_promise"].count("p2") == 2
    assert led["notes"] == [dict(product_id="p2", reason="service_error")] and led["outcome"] == "promise"
    said = " ".join(agent_lines(tr))
    assert "personal loan: I'm sorry" in said, said


def test_chain_note_failure_is_retried():
    case = copy.deepcopy(CASES["PUB-01"])
    case["faults"] = [dict(tool="add_note", fail_first_n=1)]
    led, tr = run_case(B, case, ids("PUB-01") + [dict(k="no"), dict(k="no")])
    assert led["notes"] == [dict(product_id="p1", reason="refused")] and led["outcome"] == "no_promise", agent_lines(tr)


def test_chain_platform_returning_early_still_reaches_the_planned_turn():
    import sim  # noqa: F401
    from builder import selftest
    orig = selftest.route

    def route(n, V):                    # the platform ignores the planned transitions: every call comes back to step
        t = orig(n, V)
        if n.get("node_type") == "api_request" and n["name"] not in ("api_close", "api_close_nr", "api_verify") and t != "end":
            return "step"
        return t
    selftest.route = route
    try:
        led, tr = run_case(B, CASES["PUB-11"], ids_b("PUB-11") + [dict(k="yes"), dict(k="yes")])
    finally:
        selftest.route = orig
    assert len(led["promises"]) == 3 and led["outcome"] == "promise"
    assert any("recorded" in x for x in agent_lines(tr)), agent_lines(tr)
