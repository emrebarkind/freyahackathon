"""An amount split over two messages ("I can pay three hundred and" / "fifty dollars on Friday."): the platform's
extraction reads only the latest message (chat probe 680c4bd7, 11 Oct: amount 50.0), so the engine must join the
pieces. Extraction values below are the ones the platform produced in that probe."""
import copy, json, pathlib
from builder import selftest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC = json.load(open(ROOT / "eval" / "clean-runs" / "cand8-a" / "cand8-a.spec.json"))
OA = json.load(open(ROOT / "kit" / "build-the-builder" / "tools" / "openapi.json"))
CASE = [c for c in json.load(open(ROOT / "kit" / "build-the-builder" / "public-test-set.json")) if c["id"] == "PUB-01"][0]


def T(k, t, d="", a="", cut="no"):
    return dict(k=k, t=t, d=d, a=a, f="none", side="none", cut=cut)


def run(turns):
    prods = [dict(p, product_id=f"p{i + 1}") for i, p in enumerate(CASE["products"])]
    bank = selftest.GenericBank(copy.deepcopy(SPEC), CASE["identity"], prods)
    head = [T("confirmed", "Yes, this is Daniel Reyes."), dict(k="answer", t="14 March 1988.", norm="1988-03-14"),
            dict(k="answer", t="4471.", norm="4471")]
    led, tr = selftest.simulate(SPEC, dict(customer_id="c", **CASE["variables"]), bank, head + turns, openapi=OA, max_steps=4000)
    return led, [x[1] for x in tr if x[0] == "agent"]


def test_amount_split_over_two_messages_is_joined():
    led, said = run([T("proposes", "I can pay three hundred and", cut="yes"),
                     T("proposes", "fifty dollars on Friday.", d="Friday", a=50.0),
                     T("yes", "Yes, I confirm.")])
    assert led["promises"] == [("p1", 350.0, "2026-10-16")]
    assert not any("126" in x for x in said)                     # never treated as below the floor


def test_a_plain_small_amount_is_not_inflated():
    led, said = run([T("proposes", "I can pay fifty dollars on Friday.", d="Friday", a=50.0)])
    assert any("126" in x for x in said)                           # below the floor: the floor is offered
