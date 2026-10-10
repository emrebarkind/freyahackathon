import datetime as dt
import re
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


def test_payment_date_forms():
    T = TODAY
    cases = {"Friday next week": "2026-10-23", "next week Friday": "2026-10-23", "the Friday after next": "2026-10-30",
             "maybe the 20th": "2026-10-20", "I will decide, the 20th": "2026-10-20", "a week from today": "2026-10-21",
             "in three days": "2026-10-17", "not today, but Friday": "2026-10-16", "I can't pay today, maybe Monday": "2026-10-19",
             "October twenty second": "2026-10-22", "a week on Friday": "2026-10-23"}
    for t, e in cases.items():
        assert cal.parse_spoken_date(t, T).isoformat() == e, t
    assert cal.parse_spoken_date("next week", T) is None


# day before the month -> year after it; month first -> day right after it, then the year
BIRTH_SPLIT = {"seventeen May eighty-six": "1986-05-17", "thirty January one nine eight four": "1984-01-30",
               "the fourteenth of March nineteen eighty-eight": "1988-03-14",
               "twenty-one August nineteen ninety-two": "1992-08-21",
               "thirty-first of December nineteen seventy-five": "1975-12-31",
               "March fourteenth nineteen eighty-eight": "1988-03-14", "May 17th 1986": "1986-05-17",
               "August twenty-one nineteen ninety-two": "1992-08-21", "January eight 1991": "1991-01-08",
               "June 3rd, 1987": "1987-06-03", "Jan 30 1984": "1984-01-30",
               "August twenty nineteen ninety-two": "1992-08-20", "May 19th 86": "1986-05-19",
               "seventeen May two thousand five": "2005-05-17", "1988 March 14": "1988-03-14",
               "nineteen eighty eight, the fourteenth of March": "1988-03-14",
               "it may be March 3rd 1987": "1987-03-03"}


def test_birth_date_split_around_month():
    for t, e in BIRTH_SPLIT.items():
        assert cal.parse_birth_date(t) == e, t
    # a month followed only by a year phrase has no day; a day is never taken from inside the year
    for t in ("March nineteen eighty-eight", "December 1990", "January twenty twenty", "fourteen March",
              "thirty February nineteen ninety", "", None, 42, ["x"]):
        assert cal.parse_birth_date(t) == "", t


def test_year_prefix_is_partial():
    for t in ("nineteen", "twenty", "two thousand", "one nine", "two zero", "nineteen oh", "it was nineteen"):
        assert cal.year_is_prefix(t), t
        assert cal.spoken_year(t) is None, t
        assert cal.spoken_year(cal._btokens(t)) is None, t
    for t, y in (("84", 1984), ("eighty-four", 1984), ("nineteen eighty-four", 1984), ("nineteen eighty four", 1984),
                 ("one nine eight four", 1984), ("two thousand and one", 2001), ("two thousand five", 2005),
                 ("twenty twenty", 2020), ("1984", 1984), ("eighty-six", 1986), ("oh five", 2005)):
        assert not cal.year_is_prefix(t), t
        assert cal.spoken_year(t) == y, t
    # the engine's year question parses "1 january <answer>"
    assert cal.parse_birth_date("1 january nineteen") == ""
    assert cal.parse_birth_date("1 january two thousand") == ""
    assert cal.parse_birth_date("1 january eighty-four") == "1984-01-01"
    assert not cal.year_is_prefix("") and not cal.year_is_prefix(None) and cal.spoken_year(None) is None


def test_last_weekday_wins():
    T = TODAY
    cases = {"Friday, actually no, Thursday": "2026-10-15", "Monday or rather Wednesday": "2026-10-21",
             "Thursday, no, Friday": "2026-10-16", "Monday, hmm, Wednesday": "2026-10-21",
             "Thursday, not Friday": "2026-10-15", "Monday, no, Friday next week": "2026-10-23",
             "Monday, no, next Friday": "2026-10-23", "next Monday, or Wednesday": "2026-10-21",
             "not this Friday but next Friday": "2026-10-23", "next week maybe Friday": "2026-10-23"}
    for t, e in cases.items():
        assert cal._parse_spoken_date(t, T).isoformat() == e, t
        assert cal.parse_spoken_date(t, T).isoformat() == e, t


def test_relative_word_beats_stray_number():
    T = TODAY
    cases = {"tomorrow, I get paid at 5": "2026-10-15", "tomorrow, I get paid on 5": "2026-10-15",
             "tomorrow, 25 is payday": "2026-10-15", "today, I get 10 back": "2026-10-14",
             "day after tomorrow, I have 3 kids": "2026-10-16", "first thing tomorrow": "2026-10-15",
             "give me a second, tomorrow": "2026-10-15",
             # a real date still wins: ordinal, 'the', a month next to it, or after a correction marker
             "tomorrow, sorry, the 20th": "2026-10-20", "tomorrow, sorry, 20": "2026-10-20",
             "tomorrow or the 20th": "2026-10-20", "tomorrow, October 22": "2026-10-22",
             "tomorrow, the twentieth": "2026-10-20", "day after tomorrow, actually the 20th": "2026-10-20",
             "the 20th, sorry, tomorrow": "2026-10-15", "the first of November": "2026-11-01"}
    for t, e in cases.items():
        assert cal._parse_spoken_date(t, T).isoformat() == e, t
        assert cal.parse_spoken_date(t, T).isoformat() == e, t
    assert cal._parse_spoken_date("Friday", None) is None and cal.parse_spoken_date(None, T) is None


CODES = {"it's SW1A 1AA": "SW1A1AA", "S W one A one A A": "SW1A1AA",
         "sierra whiskey one alpha, one alpha alpha": "SW1A1AA", "E C two A, four D Q": "EC2A4DQ",
         "double one": "11", "triple seven": "777", "oh oh seven": "007", "my postcode is SW1A 1AA": "SW1A1AA",
         "My postcode is S W one A, one A A.": "SW1A1AA", "I think it's E C two A four D Q": "EC2A4DQ",
         "S for Sugar W for William one A, one double A": "SW1A1AA", "B as in Bravo one zero": "B10",
         "O for Oscar": "O", "X-ray, oh, nine": "X09", "W ten five A A": "W105AA", "ec2a 4dq": "EC2A4DQ",
         "the number is double alpha twenty one": "AA21", "": "", None: ""}


def test_spoken_code():
    for t, e in CODES.items():
        assert cal.spoken_code(t) == e, t


def test_runtime_source_rules():
    src = (pathlib.Path(__file__).resolve().parent.parent / "builder" / "runtime" / "cal.py").read_text()
    assert "{{" not in src and "}}" not in src
    imports = set(re.findall(r"^\s*(?:import|from)\s+(\w+)", src, re.M))
    assert imports <= set(["json", "re", "datetime"]), imports
