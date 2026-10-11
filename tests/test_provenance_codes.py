"""Critical-policy evidence (builder/policy.py, extract.apply_audit) and code validation against the brief and API."""
import copy
import datetime
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import test_engine_edge as E  # noqa: E402
from builder import extract, policy, spec_model  # noqa: E402
from builder.runtime import engine  # noqa: E402

O = json.load(open(ROOT / "kit" / "build-the-builder" / "tools" / "openapi.json"))

POLICY = ("4. Count every proposal against the band's limit. 5. A step that repeats an earlier proposal is skipped "
          "and still counts against the limit. 6. The floor is 10% of the past-due amount, rounded up to the next "
          "whole euro. 7. The opening question is not a proposal.")
MEMO = ("MEMO 3 March: rule 5 is withdrawn. From today a skipped step does not count against the limit.")
DOCS = POLICY + "\n" + MEMO


class T:
    def __init__(self):
        self.notes = []

    def note(self, s):
        self.notes.append(s)


def base():
    return {"rules": {}, "products": {}, "identity": {}, "events": {}}


# ---------------------------------------------------------------- deterministic checks of the records

def test_a_fabricated_quotation_is_an_error():
    spec = base()
    spec["rules"]["skipped_repeat_counts"] = False
    spec["policy"] = {"rules.skipped_repeat_counts": {"kind": "explicit", "quotes": ["Skipped steps are free of charge and never count."]}}
    errs, _ = policy.check(spec, DOCS)
    assert len(errs) == 1 and "not in the materials" in errs[0]


def test_a_legitimate_derived_policy_passes_and_needs_its_derivation():
    spec = base()
    spec["products"]["floor_round"] = "up:1"
    rec = {"kind": "derived", "quotes": ["The floor is 10% of the past-due amount, rounded up to the next whole euro."],
           "derivation": "rounded up to the next whole euro = round up to a step of 1"}
    spec["policy"] = {"products.floor_round": rec}
    assert policy.check(spec, DOCS)[0] == []
    rec.pop("derivation")
    assert "derivation" in policy.check(spec, DOCS)[0][0]


def test_missing_evidence_is_uncertain_not_unsupported():
    spec = base()
    errs, report = policy.check(spec, DOCS)
    assert errs == [] and not spec.get("unsupported_rules")
    assert report["rules.skipped_repeat_counts"].startswith("no evidence recorded: true (engine default)")
    assert "rules.skipped_repeat_counts" in "".join(policy.uncertain(report))
    assert spec_model.critical(spec) == []               # uncertainty is reported, not turned into a gap


def test_unspecified_keeps_the_default_and_unsupported_controls_the_verdict():
    spec = base()
    spec["rules"]["promise_retries"] = 0
    spec["policy"] = {"rules.promise_retries": {"kind": "unspecified", "assumption": "never retried"}}
    assert "unspecified" in policy.check(spec, DOCS)[0][0]          # silent materials cannot give a non-default
    spec["rules"].pop("promise_retries")
    spec["policy"]["rules.promise_retries"]["assumption"] = "retried once"
    assert policy.check(spec, DOCS)[0] == [] and policy.assumptions(spec) == ["rules.promise_retries: retried once"]
    spec["policy"]["products.floor_round"] = {"kind": "unsupported", "requirement": "round the floor to the nearest 0.05 above 100",
                                              "gap": "no conditional rounding"}
    policy.check(spec, DOCS)
    assert any("0.05" in g for g in spec_model.critical(spec))


# ---------------------------------------------------------------- the audit's view and verdicts

def test_the_audit_sees_defaults_as_values():
    rows = {r["path"]: r for r in policy.table(base())}
    assert rows["rules.skipped_repeat_counts"]["value"] is True and rows["rules.skipped_repeat_counts"]["engine_default"]
    assert "engine_default" in extract.audit_prompt(dict(base(), bands=[], ladder=[], calendar={}, callback={}))


def test_a_default_contradicting_its_source_is_corrected_or_left_unresolved():
    spec = base()                                       # skipped_repeat_counts unset: the default (counts) applies
    fixed = extract.apply_audit(spec, {"changes": {"rules.skipped_repeat_counts": False,
                                                   "policy.rules.skipped_repeat_counts": {"kind": "explicit", "quotes": [MEMO[13:]]}},
                                       "verdicts": {"rules.skipped_repeat_counts": "contradicted"}}, T())
    assert fixed["rules"]["skipped_repeat_counts"] is False and fixed["policy_audit"]["unresolved"] == []
    assert policy.check(fixed, DOCS)[0] == []
    left = extract.apply_audit(base(), {"changes": {}, "verdicts": {"rules.skipped_repeat_counts": "contradicted"}}, T())
    assert any("skipped_repeat_counts" in g for g in spec_model.critical(left))


def test_a_real_quote_that_does_not_support_the_value():
    spec = base()
    spec["rules"]["opening_is_attempt"] = True          # non-default, quoted with a real but unrelated sentence
    spec["policy"] = {"rules.opening_is_attempt": {"kind": "explicit", "quotes": ["Count every proposal against the band's limit."]}}
    assert policy.check(spec, DOCS)[0] == []           # the quote exists: only the audit can judge support
    fixed = extract.apply_audit(spec, {"changes": {}, "verdicts": {"rules.opening_is_attempt": "quote_does_not_support"}}, T())
    assert any("opening_is_attempt" in g for g in spec_model.critical(fixed))
    dflt = extract.apply_audit(base(), {"changes": {}, "verdicts": {"rules.first_ask": "quote_does_not_support"}}, T())
    assert dflt["policy"]["rules.first_ask"]["kind"] == "unspecified" and spec_model.critical(dflt) == []


def test_a_memo_overriding_an_earlier_policy():
    spec = base()
    spec["rules"]["skipped_repeat_counts"] = True       # read from rule 5, which the memo withdrew
    spec["policy"] = {"rules.skipped_repeat_counts": {"kind": "explicit", "quotes": ["A step that repeats an earlier proposal is skipped and still counts against the limit."]}}
    assert policy.check(spec, DOCS)[0] == []           # the superseded sentence is real text
    fixed = extract.apply_audit(spec, {"changes": {"rules.skipped_repeat_counts": False,
                                                   "policy.rules.skipped_repeat_counts": {"kind": "explicit", "quotes": ["From today a skipped step does not count against the limit."]}},
                                       "verdicts": {"rules.skipped_repeat_counts": "contradicted"}}, T())
    assert fixed["rules"]["skipped_repeat_counts"] is False and policy.check(fixed, DOCS)[0] == []


def test_a_repair_keeps_the_audit_verdicts():
    old = {"policy_audit": {"verdicts": {}, "unresolved": ["x"]}}
    assert extract.carry_audit(old, {})["policy_audit"]["unresolved"] == ["x"]


# ---------------------------------------------------------------- codes

BRIEF_CODES = ("| outcome | reasons |\n| no_promise | refused, hardship |\n| paid | |\n"
               "Notes: PAID, NOPTP.\nMEMO: from 2026-11-02 the note PAID is replaced by CLAIMED_PAID. "
               "The hardship reason is now renamed money_trouble.")


def codes(spec, openapi=None, docs=BRIEF_CODES):
    return policy.check_codes(spec, openapi or {}, docs, lambda f: None)


def code_spec():
    return {"events": {"refused": {"outcome": "no_promise", "reason": "refused", "note": "NOPTP"},
                       "hardship": {"outcome": "no_promise", "reason": "money_trouble"},
                       "paid": {"outcome": "paid", "reason": "", "note": "PAID"}},
            "code_tables": {"reason": {"no_promise": ["refused", "money_trouble"]}, "note": ["PAID", "NOPTP"]}}


def test_an_undefined_code_is_found_before_deployment():
    s = code_spec()
    s["events"]["refused"]["reason"] = "paid_claimed"
    errs, _ = codes(s)
    assert len(errs) == 1 and "paid_claimed" in errs[0] and "not defined" in errs[0]


def test_a_memo_may_introduce_or_replace_a_code():
    s = code_spec()                                     # money_trouble: the memo's renamed reason, in the table
    s["event_changes"] = [{"event": "paid", "from": "2026-11-02", "set": {"note": "CLAIMED_PAID"}}]
    assert codes(s) == ([], [])
    s["event_changes"][0]["set"]["note"] = "CLAIMD_PAID"          # a typo: in no document
    assert "CLAIMD_PAID" in codes(s)[0][0]


def test_without_enum_or_table_nothing_is_restricted():
    s = code_spec()
    s.pop("code_tables")
    s["events"]["refused"]["reason"] = "customer_said_no"     # in no document: reported, not an error
    errs, warns = codes(s)
    assert errs == [] and "customer_said_no" in warns[0]


def test_the_validator_reports_code_errors_with_the_materials():
    spec = copy.deepcopy(E.A)
    spec["code_tables"] = {"reason": {"no_promise": ["refused"]}}
    errs = extract.validate(spec, O, json.dumps(spec["events"]) + " refused")
    assert any("not defined" in e for e in errs)


def test_date_boundaries_select_the_code_and_other_events_keep_theirs():
    s = code_spec()
    s["event_changes"] = [{"event": "paid", "from": "2026-11-02", "set": {"note": "CLAIMED_PAID"}}]
    engine.S = s
    try:
        got = {}
        for d in ("2026-11-01", "2026-11-02", "2026-11-03"):
            engine.TODAY[0] = datetime.date.fromisoformat(d)
            got[d] = (engine.ev("paid").get("note"), engine.ev("refused").get("note"), engine.ev("hardship").get("reason"))
        assert got == {"2026-11-01": ("PAID", "NOPTP", "money_trouble"),
                       "2026-11-02": ("CLAIMED_PAID", "NOPTP", "money_trouble"),
                       "2026-11-03": ("CLAIMED_PAID", "NOPTP", "money_trouble")}
    finally:
        engine.TODAY[0] = None


# ---------------------------------------------------------------- found by eval/fresh/f1 (first run 9/20)

def test_day_of_month_rolls_before_the_weekend_move_only_when_the_brief_says_so():
    from builder.runtime import cal
    spec = copy.deepcopy(E.A)
    from builder import compile as comp
    s = comp.apply_defaults(spec, O)
    s["calendar"]["holidays"] = []
    s["rules"]["deadline_adjust"] = "next_business_day"
    rule = {"kind": "day_of_month", "n": 15, "roll_if_before_today": True}
    for b in s["bands"]:
        b["deadline"] = dict(rule)
    engine.S = s
    cal.P = dict(workdays=s["calendar"]["workdays"], holidays=[])
    typ = list(s["products"]["names"])[0]
    raw = {"product_id": "p1", "type": typ, "past_due": 300.0, "days_late": s["bands"][0]["min"],
           s["products"]["floor_field"][typ]: 30.0}
    dl = lambda now: engine.product_facts({"now": now + "T11:00"}, raw)["deadline"]
    assert [dl("2026-10-14"), dl("2026-10-15"), dl("2026-10-16")] == ["2026-10-15", "2026-10-15", "2026-11-16"]
    assert dl("2026-11-16") == "2026-11-16"            # default order: the moved date (Mon 16th) is not before today
    for b in s["bands"]:
        b["deadline"]["roll_before_adjust"] = True     # "moved forward only after that rollover"
    assert dl("2026-11-16") == "2026-12-15" and dl("2026-10-15") == "2026-10-15"


def test_a_band_the_engine_cannot_compute_fails_the_self_test_and_the_verdict():
    from builder import selftest, build
    spec = copy.deepcopy(E.A)
    spec["bands"][-1]["deadline"] = {"kind": "day_of_the_month", "n": 15}
    r = dict((n, ok) for n, ok, _ in selftest.run_all(spec, O))
    assert r["every band and product type gives a deadline and a floor"] is False

    class Tr:
        def note(self, s):
            self.last = s

        def end(self):
            pass
    tr = Tr()
    try:
        build.finish(tr, {}, {"failed": [], "api": ["band late: deadline kind 'x' invalid"]})
        assert False, "must exit INCOMPLETE"
    except SystemExit as e:
        assert e.code == 3 and "spec problem left" in tr.last


def test_floor_full_below_only_when_the_brief_says_so():
    from builder.runtime import cal
    from builder import compile as comp
    s = comp.apply_defaults(copy.deepcopy(E.A), O)
    engine.S = s
    cal.P = dict(workdays=s["calendar"]["workdays"], holidays=s["calendar"]["holidays"])
    s["products"]["floor_field"] = {}
    s["products"]["floor_pct"], s["products"]["floor_round"] = 25, "up_unit"
    typ = list(s["products"]["names"])[0]
    fl = lambda full: engine.product_facts({"now": "2026-10-14T11:00"}, {"product_id": "p", "type": typ, "past_due": full,
                                                                          "days_late": s["bands"][0]["min"]})["floor"]
    assert (fl(72.4), fl(333.33)) == (19.0, 84.0)
    s["products"]["floor_full_below"] = 100                 # f1: "if the overdue amount is below 100, the whole amount"
    assert (fl(72.4), fl(333.33), fl(100.0)) == (72.4, 84.0, 25.0)


# ---------------------------------------------------------------- Phase 2 step 5 (implicit policy audit)

def test_week_deadlines_roll_by_a_week_and_next_month_days_are_not_capped_at_28():
    from builder.runtime import cal
    from builder import compile as comp
    s = comp.apply_defaults(copy.deepcopy(E.A), O)
    s["calendar"]["holidays"] = []
    engine.S = s
    cal.P = dict(workdays=s["calendar"]["workdays"], holidays=[])
    typ = list(s["products"]["names"])[0]
    raw = {"product_id": "p1", "type": typ, "past_due": 300.0, "days_late": s["bands"][0]["min"],
           s["products"]["floor_field"][typ]: 30.0}
    s["bands"][0]["deadline"] = {"kind": "end_of_week", "roll_if_not_after_today": True}
    assert engine.product_facts({"now": "2026-10-16T11:00"}, raw)["deadline"] == "2026-10-23"   # Friday: next Friday
    assert cal.deadline(datetime.date(2026, 10, 31), {"kind": "day_of_next_month", "n": 30}) == datetime.date(2026, 11, 30)
