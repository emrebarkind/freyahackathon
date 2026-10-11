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
