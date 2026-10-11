"""The independent oracle reading (builder/oracle.py): comparison and the one targeted repair round."""
import copy
import re
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from builder import extract, oracle  # noqa: E402


def blind(pkg):
    key = json.load(open(ROOT / pkg / "key.json"))
    second = {c["id"]: c["expect"] for c in json.load(open(ROOT / pkg / "second_reading.json"))}
    checks = copy.deepcopy(key["checks"])
    for c in checks:
        c["expect"] = second[c["id"]]
    return checks, json.load(open(ROOT / pkg / "openapi.json"))


class T:
    def __init__(self):
        self.notes = []

    def note(self, s):
        self.notes.append(s)

    def model_call(self, *a):
        pass


def test_the_oracle_flags_exactly_the_real_failures_of_a_first_attempt():
    checks, api = blind("eval/fresh/f1")
    first = json.load(open(ROOT / "eval/clean-runs/fresh-f1-first/fresh-f1.spec.json"))
    dis, unusable = oracle.compare(first, api, checks)
    assert sorted(d["id"] for d in dis) == ["C12", "C13", "C4", "C7"] and not unusable
    good = json.load(open(ROOT / "eval/clean-runs/fresh-f1-retest/fresh-f1-retest.spec.json"))
    assert oracle.compare(good, api, checks)[0] == []                      # no false flag on a correct spec


def test_the_oracle_never_sees_the_spec_format():
    m = extract.materials_for([("brief.md", "1. A rule.")], {"paths": {}})
    assert "1. A rule." in m and extract.DOC[:200] not in m \
        and not re.search(r"\bspec\b", oracle.INSTRUCTIONS.lower())


def test_one_targeted_repair_is_accepted_only_if_disagreements_drop(monkeypatch):
    checks, api = blind("eval/fresh/f1")
    first = json.load(open(ROOT / "eval/clean-runs/fresh-f1-first/fresh-f1.spec.json"))
    good = json.load(open(ROOT / "eval/clean-runs/fresh-f1-retest/fresh-f1-retest.spec.json"))
    fix = {"products.floor_full_below": good["products"]["floor_full_below"], "bands.1.deadline": good["bands"][1]["deadline"]}
    monkeypatch.setattr(extract.claude, "ask_json", lambda *a, **k: {"changes": fix, "verdicts": {}})
    out = extract.oracle_round(copy.deepcopy(first), checks, "base", api, T(), None)
    assert out["oracle_report"]["disagreements"] == [] and out["products"]["floor_full_below"] == good["products"]["floor_full_below"]
    monkeypatch.setattr(extract.claude, "ask_json", lambda *a, **k: {"changes": {"bands.0.attempts": 9}, "verdicts": {}})
    out = extract.oracle_round(copy.deepcopy(first), checks, "base", api, T(), None)
    assert out["bands"][0]["attempts"] == first["bands"][0]["attempts"]           # worse or no better: rejected
    assert len(out["oracle_report"]["disagreements"]) == 4                         # and reported, never silent


def test_dated_value_changes_apply_from_their_day_and_never_change_the_base():
    from builder.runtime import engine, cal
    import datetime
    s = json.load(open(ROOT / "eval/clean-runs/m12-h2/m12-h2.spec.json"))
    api = json.load(open(ROOT / "eval/heldout/h2/openapi.json"))
    s["bands"][0]["deadline"] = {"kind": "business_days_after", "n": 7}
    s["products"]["floor_pct"]["overdraft"] = 25
    s["changes"] = [{"from": "2026-10-30", "set": {"bands.0.deadline": {"kind": "business_days_after", "n": 5},
                                                    "products.floor_pct.overdraft": 20}}]
    assert extract.validate(copy.deepcopy(s), api) == []
    eff = engine.effective(s, datetime.date(2026, 10, 30))
    assert eff["bands"][0]["deadline"]["n"] == 5 and s["bands"][0]["deadline"]["n"] == 7
    assert engine.effective(s, datetime.date(2026, 10, 29)) is s
    checks, _ = blind("eval/heldout/h2")
    live = json.load(open(ROOT / "eval/audit_cases/oracle_live_f1_h2.json"))["h2"]
    assert oracle.compare(copy.deepcopy(s), api, live)[0] == []          # the calls on 29 Oct get the old rules
    bad = copy.deepcopy(s)
    bad["changes"][0]["set"]["bands.0.deadline"] = {"kind": "no_such_kind"}
    assert any("changes from 2026-10-30" in e for e in extract.validate(bad, api))
