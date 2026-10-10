import datetime as dt
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from builder.runtime import cal

A_HOLIDAYS = ["2026-10-26", "2026-11-11", "2026-11-26", "2026-12-25", "2027-01-01"]
TODAY = dt.date(2026, 10, 14)  # Wednesday, every public case


def setup_module(_):
    cal.P = dict(workdays=[0, 1, 2, 3, 4], holidays=A_HOLIDAYS)


def test_deadlines_brief_a():
    assert cal.deadline(TODAY, {"kind": "business_days_after", "n": 7}) == dt.date(2026, 10, 23)   # PUB-04, PUB-13 loan
    assert cal.deadline(TODAY, {"kind": "business_days_after", "n": 12}) == dt.date(2026, 11, 2)   # skips 26 Oct holiday


def test_week_rules():
    assert cal.last_business_day_of_week(TODAY) == dt.date(2026, 10, 16)
    assert cal.parse_spoken_date("this Friday", TODAY) == dt.date(2026, 10, 16)
    assert cal.parse_spoken_date("next Friday", TODAY) == dt.date(2026, 10, 23)
    fri = dt.date(2026, 10, 16)
    assert cal.parse_spoken_date("next Friday", fri) == dt.date(2026, 10, 23)
    assert cal.parse_spoken_date("tomorrow", TODAY) == dt.date(2026, 10, 15)


def test_holiday_and_next_business_day():
    d = cal.parse_spoken_date("Monday the 26th", TODAY)
    assert d == dt.date(2026, 10, 26) and not cal.is_business_day(d)
    assert cal.next_business_day(d) == dt.date(2026, 10, 27)   # PUB-07
    assert cal.parse_spoken_date("the twenty-second of October", TODAY) == dt.date(2026, 10, 22)
    assert cal.parse_spoken_date("6 November", TODAY) == dt.date(2026, 11, 6)
    assert cal.parse_spoken_date("30 October", TODAY) == dt.date(2026, 10, 30)


def test_numbers_and_birthdates():
    assert cal.words_to_number("four hundred and fifty-five") == 455
    assert cal.words_to_number("six hundred thirty-seven fifty") is not None
    assert cal.words_to_number("637.50") == 637.5
    assert cal.digits_only("four four seven one") == "4471"
    assert cal.digits_only("44 71") == "4471"
    assert cal.parse_birth_date("14 March 1988") == "1988-03-14"
    assert cal.parse_birth_date("the fourteenth of March nineteen eighty-eight") == "1988-03-14"
    assert cal.parse_birth_date("12/07/1991") == "1991-07-12"
    assert cal.parse_birth_date("March 14, 1988") == "1988-03-14"


BIRTH = {"Twenty-eighth of April nineteen ninety-three": "1993-04-28", "April the third, two thousand and one": "2001-04-03",
         "eighth of January ninety-one": "1991-01-08", "5 December 75": "1975-12-05", "March fourteenth, nineteen eighty-eight": "1988-03-14",
         "seventeenth may eighty six": "1986-05-17", "twentieth of december two thousand and five": "2005-12-20", "Jan 30 1984": "1984-01-30"}
DIGITS = {"zero three five eight": "0358", "forty-four seventy-one": "4471", "four thousand four hundred seventy-one": "4471",
          "sixty-six thirty": "6630", "double seven two one": "7721", "fifteen oh two": "1502", "twenty-two nineteen": "2219"}


def test_spoken_forms():
    for t, e in BIRTH.items():
        assert cal.parse_birth_date(t) == e, t
    for t, e in DIGITS.items():
        assert cal.digits_only(t) == e, t


def test_spoken_times_and_corrections():
    from builder.runtime import engine
    import json, pathlib
    engine.S = json.load(open(pathlib.Path(__file__).resolve().parent.parent / "specs" / "brief-a.gold.json"))
    cases = {"tomorrow at ten, sorry, I mean eleven in the morning": ("2026-10-15", "11:00"),
             "Friday at two, actually make that three": ("2026-10-16", "15:00"),
             "tomorrow, maybe quarter to six in the evening": ("2026-10-15", "17:45"),
             "around seven tonight": ("2026-10-14", "19:00"), "tomorrow at 11": ("2026-10-15", "11:00"),
             "tomorrow morning around eleven": ("2026-10-15", "11:00"), "tomorrow at noon": ("2026-10-15", "12:00")}
    for t, (d, h) in cases.items():
        gd, gh = engine.parse_callback(t, TODAY, dict())
        assert (gd.isoformat(), gh) == (d, h), t
    assert cal.parse_spoken_date("the 21st, sorry, I mean the 20th", TODAY).isoformat() == "2026-10-20"
    assert cal.parse_spoken_date("Friday, actually no, Thursday", TODAY).isoformat() == "2026-10-15"
