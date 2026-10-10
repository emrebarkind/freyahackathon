"""Property-based tests (Hypothesis): general rules instead of hand-picked examples.

Oracles: our own number/date writers produce the words a customer would say; the parsers must give the value back.
Packing: what the compiler embeds in the code node must decode to exactly what it packed, on one physical line.
Engine: random customer scripts must always end with close_call and never break the brief's hard limits.
"""
import copy
import datetime
import json
import os
import pathlib
import sys

from hypothesis import HealthCheck, assume, given, settings, strategies as st

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
os.environ.setdefault("FREYA_BANK_TEAM_KEY", "local-test-key-0000")
from builder import compile as comp  # noqa: E402
from builder.runtime import cal  # noqa: E402

N = int(os.environ.get("HYPO_N", "300"))            # HYPO_N=3000 for a deep run
FAST = settings(max_examples=N, deadline=None, suppress_health_check=[HealthCheck.too_slow])

UNITS = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen " \
        "seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
ORD = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth",
       10: "tenth", 11: "eleventh", 12: "twelfth", 13: "thirteenth", 14: "fourteenth", 15: "fifteenth", 16: "sixteenth",
       17: "seventeenth", 18: "eighteenth", 19: "nineteenth", 20: "twentieth", 30: "thirtieth"}
MONTHS = "January February March April May June July August September October November December".split()


def words(n, hyphen=True, and_=False):
    """0..999999 in English words, the way people say them."""
    if n < 20:
        return UNITS[n]
    if n < 100:
        return TENS[n // 10] + (("-" if hyphen else " ") + UNITS[n % 10] if n % 10 else "")
    if n < 1000:
        rest = n % 100
        return UNITS[n // 100] + " hundred" + ((" and " if and_ else " ") + words(rest, hyphen) if rest else "")
    rest = n % 1000
    return words(n // 1000, hyphen, and_) + " thousand" + ((" and " if and_ and rest < 100 else " ") + words(rest, hyphen, and_) if rest else "")


def ordinal_words(d):
    if d in ORD:
        return ORD[d]
    return TENS[d // 10] + "-" + ORD[d % 10]


def year_words(y):
    if 2000 <= y <= 2009:
        return "two thousand" + (" and " + UNITS[y - 2000] if y > 2000 else "")
    hi, lo = divmod(y, 100)
    return words(hi) + " " + ("hundred" if lo == 0 else ("oh " + UNITS[lo] if lo < 10 else words(lo)))


# ------------------------------------------------------------------------------------------- spoken numbers
@FAST
@given(st.integers(min_value=0, max_value=99999), st.booleans(), st.booleans())
def test_number_words_round_trip(n, hyphen, and_):
    assert cal.words_to_number(words(n, hyphen, and_)) == n, words(n, hyphen, and_)


@FAST
@given(st.lists(st.integers(min_value=0, max_value=9), min_size=4, max_size=4))
def test_four_digits_said_one_by_one(ds):
    said = " ".join(UNITS[d] for d in ds)
    assert cal.digits_only(said) == "".join(map(str, ds)), said


# ------------------------------------------------------------------------------------------- dates
@FAST
@given(st.dates(min_value=datetime.date(1935, 1, 1), max_value=datetime.date(2008, 12, 31)), st.integers(0, 3))
def test_birth_dates_said_in_words(d, form):
    said = [f"the {ordinal_words(d.day)} of {MONTHS[d.month - 1]} {year_words(d.year)}",
            f"{MONTHS[d.month - 1]} {ordinal_words(d.day)}, {year_words(d.year)}",
            f"{d.day} {MONTHS[d.month - 1]} {d.year}",
            f"{ordinal_words(d.day)} {MONTHS[d.month - 1]} {year_words(d.year)}"][form]
    assert cal.parse_birth_date(said, "dmy") == d.isoformat(), said


@FAST
@given(st.dates(min_value=datetime.date(2026, 10, 14), max_value=datetime.date(2026, 12, 31)), st.integers(0, 3))
def test_payment_dates_said_by_customers(d, form):
    today = datetime.date(2026, 10, 14)
    said = [f"the {ordinal_words(d.day)} of {MONTHS[d.month - 1]}", f"{MONTHS[d.month - 1]} {ordinal_words(d.day)}",
            f"{d.day} {MONTHS[d.month - 1]}", f"on the {d.day}th of {MONTHS[d.month - 1]}"][form]
    assume(not (form == 3 and d.day in (1, 2, 3, 21, 22, 23, 31)))
    assert cal._parse_spoken_date(said, today, {"next_weekday": "following_week"}) == d, said


@FAST
@given(st.text(max_size=80))
def test_parsers_never_raise_and_return_well_formed_values(t):
    today = datetime.date(2026, 10, 14)
    d = cal._parse_spoken_date(t, today, {})
    assert d is None or isinstance(d, datetime.date)
    hm = cal.spoken_time(t)
    assert hm is None or (len(hm) == 5 and 0 <= int(hm[:2]) <= 23 and 0 <= int(hm[3:]) <= 59)
    b = cal.parse_birth_date(t, "dmy")
    assert b == "" or datetime.date.fromisoformat(b)
    assert all(c.isalnum() and c.isascii() for c in cal.spoken_code(t))
    assert cal.digits_only(t).isdigit() or cal.digits_only(t) == ""


@FAST
@given(st.integers(8, 18), st.sampled_from([0, 15, 30, 45]), st.integers(0, 2))
def test_callback_times(h, m, form):
    h12 = h - 12 if h > 12 else h
    ap = "pm" if h >= 12 else "am"
    said = [f"{h12}:{m:02d}{ap}", f"at {h12}:{m:02d} {ap}", f"{h:02d}:{m:02d}"][form]
    assert cal.spoken_time(said) == f"{h:02d}:{m:02d}", said


# ------------------------------------------------------------------------------------------- code node packing
@FAST
@given(st.text(min_size=1, max_size=400))
def test_lzw_round_trip(t):
    alpha, packed = comp.lzw_pack(t)
    ns = dict()
    exec(comp.LZW_DECODER, ns)
    assert ns["_lzw"](alpha, packed) == t


@FAST
@given(st.text(max_size=200))
def test_one_line_literal_is_one_line_and_exact(t):
    lit = comp.one_line_literal(t)
    assert eval(lit) == t
    assert len(lit.splitlines()) <= 1, repr(lit)          # the platform splits the code into lines and indents them


JSON = st.recursive(st.none() | st.booleans() | st.integers(-10**6, 10**6) | st.text(max_size=20),
                    lambda c: st.lists(c, max_size=4) | st.dictionaries(st.text(max_size=8), c, max_size=4), max_leaves=20)


@FAST
@given(st.dictionaries(st.text(max_size=8), JSON, max_size=5))
def test_embedded_spec_round_trips_without_double_braces(obj):
    expr = comp.embed_json(obj)
    assert "{{" not in expr and "}}" not in expr
    assert eval(expr, {"json": json}) == obj


# ------------------------------------------------------------------------------------------- engine invariants
KINDS = ["yes", "no", "proposes", "too_much", "vague", "already_paid", "dispute", "hardship", "restructure", "human",
         "robot", "scam", "not_talk", "asks_amount", "details", "question", "unclear", "none", "call_later"]
DATES = ["", "", "Friday", "tomorrow", "next week", "30 October", "the 20th", "Saturday", "15 December", "today"]


@settings(max_examples=max(150, N // 3), deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
@given(st.sampled_from(["A", "B"]), st.sampled_from(["PUB-01", "PUB-04", "PUB-06", "PUB-11", "PUB-13"]),
       st.lists(st.tuples(st.sampled_from(KINDS), st.sampled_from(DATES), st.sampled_from([None, None, 50, 300, 637, 5000]),
                          st.sampled_from(["none", "none", "all", "credit_card", "personal_loan"]), st.booleans()),
                min_size=1, max_size=25))
def test_random_customers_never_break_the_hard_rules(brief, cid, turns):
    import test_engine_edge as E
    from sim import run_case
    spec = E.A if brief == "A" else E.B
    case = copy.deepcopy(E.CASES[cid])
    script = E.ids(cid) + [dict(k=k, d=d, a=a, f=f, cut="yes" if cut else "no", t=(k + " " + d).strip()) for k, d, a, f, cut in turns]
    led, tr = run_case(spec, case, script)
    said = " ".join(t for w, t in tr if w == "agent")
    assert "{" not in said and "}" not in said, said
    ended = led["outcome"] is not None
    hung_up = tr and tr[-1] == ("customer", "<silence>")
    assert ended or hung_up, tr[-6:]
    if ended:
        assert led["calls"][-1]["tool"] == "close_call"
    today = datetime.date(2026, 10, 14)
    cal.P = dict(workdays=spec["calendar"]["workdays"], holidays=spec["calendar"]["holidays"])
    prods = {f"p{i + 1}": p for i, p in enumerate(case["products"])}
    seen = set()
    for pr in led["promises"]:
        d = datetime.date.fromisoformat(pr["date"])
        p = prods[pr["product_id"]]
        assert pr["product_id"] not in seen, "two promises for one product"
        seen.add(pr["product_id"])
        assert d >= today and cal.is_business_day(d), pr
        floor_field = spec["products"]["floor_field"].get(p["type"])
        floor = p.get(floor_field, p["past_due"])
        assert floor - 0.005 <= pr["amount"] <= p["past_due"] + 0.005, (pr, p)
        from builder.runtime import engine
        engine.S = spec
        dl = engine.product_facts(dict(now="2026-10-14T11:00"), dict(p, product_id=pr["product_id"]))["deadline"]
        assert pr["date"] <= dl, (pr, dl)
