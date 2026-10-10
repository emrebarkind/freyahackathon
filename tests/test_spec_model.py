"""The Pydantic spec model catches the spec mistakes that break the engine but pass the tool-API checks
(found with a mutation study; see README)."""
import copy
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from builder import compile as comp, extract, spec_model  # noqa: E402

O = json.load(open(ROOT / "kit" / "build-the-builder" / "tools" / "openapi.json"))
BASE = comp.apply_defaults(json.load(open(ROOT / "specs" / "brief-b.gold.json")), O)


def mutated(path, val):
    s = copy.deepcopy(BASE)
    d = s
    for k in path[:-1]:
        d = d[k]
    d[path[-1]] = val
    return s


def test_real_specs_fit_the_model():
    for f in list((ROOT / "specs").glob("*.gold.json")) + [ROOT / "submission" / n for n in
              ("brief-a.spec.json", "brief-b.spec.json", "variant-c.spec.json", "variant-d.spec.json",
               "variant-e.spec.json", "rehearsal-f.spec.json")]:
        assert spec_model.check(json.load(open(f))) == [], f


def test_validate_now_catches_the_mistakes_that_broke_the_engine():
    for path, val in ((["callback", "end"], "7pm"), (["callback", "end"], "09:00"), (["calendar", "workdays"], ["Monday"]),
                      (["ladder"], []), (["identity", "max_wrong"], "3"), (["identity", "max_wrong"], 0),
                      (["events", "refused", "outcome"], ""), (["calendar", "holidays", 0], "26/10/2026"),
                      (["bands", 1, "min"], 9), (["bands", 1, "min"], 5)):
        assert extract.validate(mutated(path, val), O), (path, val)


def test_callback_time_without_leading_zero_is_normalised():
    s = comp.apply_defaults(mutated(["callback", "start"], "9:00"), O)
    assert s["callback"]["start"] == "09:00" and spec_model.check(s) == []
