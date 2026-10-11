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
