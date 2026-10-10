"""What create_promise sends: the unit the tool API declares. The kit API takes a number in pounds (sent as is); an
integer API takes whole units, so the spec must state the unit and the engine sends whole numbers only."""
import copy
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from builder import compile as comp, extract  # noqa: E402
from builder.runtime import engine  # noqa: E402
import test_engine_edge as E  # noqa: E402

KIT = E.json.load(open(ROOT / "kit" / "build-the-builder" / "tools" / "openapi.json"))


def integer_api():
    o = copy.deepcopy(KIT)
    o["paths"]["/create_promise"]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"]["amount"]["type"] = "integer"
    return o


def test_kit_api_sends_the_pounds_value_as_is():
    s = comp.apply_defaults(copy.deepcopy(E.A), KIT)
    engine.S = s
    assert s["products"]["promise_integer"] is False
    assert engine.promise_amount({"agreed": [85.5, ""]}) == 85.5


def test_integer_api_with_pence_sends_whole_pence():
    o = integer_api()
    s = comp.apply_defaults(copy.deepcopy(E.A), o)
    s["products"]["promise_scale"] = 100
    engine.S = s
    assert s["products"]["promise_integer"] is True
    assert engine.promise_amount({"agreed": [85.5, ""]}) == 8550
    assert isinstance(engine.promise_amount({"agreed": [85.5, ""]}), int)


def test_integer_api_without_a_stated_unit_is_an_error():
    o = integer_api()
    s = comp.apply_defaults(copy.deepcopy(E.A), o)
    s["products"].pop("promise_scale", None)
    s["products"].pop("amount_scale", None)
    assert any("integer amount" in e for e in extract.validate(s, o))
    s["products"]["promise_scale"] = 1
    assert not any("integer amount" in e for e in extract.validate(s, o))
