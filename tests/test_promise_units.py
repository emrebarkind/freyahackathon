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


def _amount(monkeypatch, agreed, **products):
    monkeypatch.setattr(engine, "S", {"products": products})
    return engine.promise_amount({"agreed": [agreed, ""]})


def test_no_silent_rounding_after_unit_conversion(monkeypatch):
    assert _amount(monkeypatch, 85.5, promise_scale=100, promise_integer=True) == 8550
    assert _amount(monkeypatch, 0.29, promise_scale=100, promise_integer=True) == 29          # 28.999999... is float noise
    # whole-pound integer field, 412.37 agreed: the brief's rule decides; without one nothing is cut
    assert _amount(monkeypatch, 412.37, promise_integer=True, promise_round="up") == 413
    assert _amount(monkeypatch, 412.37, promise_integer=True, promise_round="down") == 412
    assert _amount(monkeypatch, 412.5, promise_integer=True, promise_round="nearest") == 413
    assert _amount(monkeypatch, 412.37, promise_integer=True) == 412.37
    assert _amount(monkeypatch, 85.555, promise_scale=100, promise_integer=True) == 8555.5   # a fraction of a penny: sent as is
    assert _amount(monkeypatch, 85.5) == 85.5                                                  # kit API: pounds, number


def test_unstated_rounding_for_whole_units_is_reported():
    from builder import spec_model
    o = integer_api()
    s = comp.apply_defaults(copy.deepcopy(E.A), o)
    s["products"]["promise_scale"] = 1
    assert any("no rounding rule" in r for r in spec_model.unsupported(s))
    s["products"]["promise_round"] = "down"
    assert not any("no rounding rule" in r for r in spec_model.unsupported(s))
