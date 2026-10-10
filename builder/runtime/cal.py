"""Calendar arithmetic that runs INSIDE the phone agent (Freya code nodes / hooks).

Constraints of the Freya sandbox: only `json`, `re`, `datetime` are known to import; the source must not
contain the two-character brace sequences used by Freya templating. Every brief-specific value comes from P,
a dict the compiler injects (hex-encoded JSON). Keep this file self-contained and free of other imports.
"""
import datetime
import json
import re

# Injected by the compiler. Defaults keep the module importable for local tests.
P = dict(workdays=[0, 1, 2, 3, 4], holidays=[])

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]


def parse_now(now):
    s = str(now or "").strip().replace(" ", "T")
    try:
        return datetime.datetime.fromisoformat(s[:16])
    except Exception:
        return datetime.datetime.fromisoformat(s[:10] + "T00:00")


def iso(d):
    return d.isoformat()


def is_business_day(d):
    return d.weekday() in P["workdays"] and iso(d) not in P["holidays"]


def next_business_day(d, include_self=True):
    if not include_self:
        d = d + datetime.timedelta(days=1)
    while not is_business_day(d):
        d = d + datetime.timedelta(days=1)
    return d


def add_business_days(d, n):
    """The n-th business day after d (d itself not counted). n=0 returns d."""
    k = 0
    while k < n:
        d = d + datetime.timedelta(days=1)
        if is_business_day(d):
            k += 1
    return d


def add_calendar_days(d, n):
    return d + datetime.timedelta(days=n)


def end_of_month(d):
    nxt = (d.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    return nxt - datetime.timedelta(days=1)


def week_bounds(d, offset_weeks=0):
    monday = d - datetime.timedelta(days=d.weekday()) + datetime.timedelta(weeks=offset_weeks)
    return monday, monday + datetime.timedelta(days=6)


def last_business_day_of_week(d, offset_weeks=0):
    monday, sunday = week_bounds(d, offset_weeks)
    x = sunday
    while x >= monday:
        if is_business_day(x):
            return x
        x = x - datetime.timedelta(days=1)
    return None


def weekday_in_week(today, weekday, which):
    """which='this' -> that weekday in the current Mon-Sun week; 'next' -> in the following week."""
    monday, _ = week_bounds(today, 1 if which == "next" else 0)
    return monday + datetime.timedelta(days=weekday)


def upcoming_weekday(today, weekday, include_today=False):
    delta = (weekday - today.weekday()) % 7
    if delta == 0 and not include_today:
        delta = 7
    return today + datetime.timedelta(days=delta)


def deadline(today, rule):
    """rule: dict(kind=..., n=...). kinds: business_days_after, calendar_days_after, end_of_month,
    end_of_next_month, last_business_day_of_month, fixed_date (value=YYYY-MM-DD)."""
    kind, n = rule.get("kind"), int(rule.get("n") or 0)
    if kind == "business_days_after":
        return add_business_days(today, n)
    if kind == "calendar_days_after":
        return add_calendar_days(today, n)
    if kind == "end_of_month":
        return end_of_month(today)
    if kind == "end_of_next_month":
        return end_of_month(end_of_month(today) + datetime.timedelta(days=1))
    if kind == "last_business_day_of_month":
        x = end_of_month(today)
        while not is_business_day(x):
            x = x - datetime.timedelta(days=1)
        return x
    if kind == "fixed_date":
        return datetime.date.fromisoformat(rule["value"])
    raise ValueError("unknown deadline kind " + str(kind))


# ---------------------------------------------------------------- spoken-language parsing
NUM_WORDS = {
    "zero": 0, "oh": 0, "o": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
ORD_WORDS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
    "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14,
    "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18, "nineteenth": 19,
    "twentieth": 20, "thirtieth": 30,
}


def words_to_number(text):
    """'four hundred and fifty-five point five' -> 455.5 ; 'six three three oh' -> 6330 (digit run).
    Returns None when nothing numeric is found."""
    t = str(text or "").lower().replace("-", " ").replace(",", "")
    m = re.search(r"\d+(?:\.\d+)?", t)
    if m and not re.search(r"[a-z]", t.replace("point", "").replace("and", "").replace("dollars", "").replace("euros", "").replace("pounds", "")):
        return float(m.group())
    toks = [w for w in re.findall(r"[a-z]+|\d+(?:\.\d+)?", t) if w not in ("and", "a", "dollars", "dollar", "euros", "euro", "pounds", "pound", "cents", "lira")]
    if not toks:
        return None
    # pure digit run spoken one by one: "six six three zero"
    if all(w in NUM_WORDS and NUM_WORDS[w] < 10 or re.fullmatch(r"\d", w) for w in toks) and len(toks) >= 2:
        return float("".join(str(NUM_WORDS.get(w, w)) for w in toks))
    total, cur, frac, in_frac, seen = 0.0, 0.0, "", False, False
    for w in toks:
        if w == "point":
            in_frac = True
            continue
        if in_frac:
            if w in NUM_WORDS and NUM_WORDS[w] < 10:
                frac += str(NUM_WORDS[w]); continue
            if re.fullmatch(r"\d+", w):
                frac += w; continue
            v = NUM_WORDS.get(w)
            if v is not None:
                frac += str(v); continue
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?", w):
            cur += float(w); seen = True
        elif w in NUM_WORDS:
            cur += NUM_WORDS[w]; seen = True
        elif w == "hundred":
            cur = (cur or 1) * 100; seen = True
        elif w == "thousand":
            total += (cur or 1) * 1000; cur = 0; seen = True
    if not seen:
        return None
    val = total + cur
    if frac:
        val += float("0." + frac)
    return val


def parse_spoken_date(text, today, rules=None):
    """Best-effort: returns a datetime.date or None. Handles ISO, 'today', 'tomorrow',
    '(this|next) <weekday>', bare weekday (next occurrence), '<day> <month>' / '<month> <day>' with
    digits or ordinal words, and 'the 23rd'. `rules` may set next_weekday='following_week' (default)."""
    rules = rules or {}
    t = str(text or "").lower().strip()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if "day after tomorrow" in t:
        return today + datetime.timedelta(days=2)
    if "tomorrow" in t:
        return today + datetime.timedelta(days=1)
    if re.search(r"\btoday\b|\bnow\b|right away", t):
        return today
    month = None
    for i, mn in enumerate(MONTHS):
        if re.search(r"\b" + mn[:3] + r"[a-z]*\b", t):
            month = i + 1
    day = None
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\b", t)
    if m and 1 <= int(m.group(1)) <= 31:
        day = int(m.group(1))
    else:
        tt = t.replace("-", " ")
        for w, v in sorted(ORD_WORDS.items(), key=lambda kv: -len(kv[0])):
            mm = re.search(r"\b(twenty|thirty)\s+" + w + r"\b", tt)
            if mm:
                day = NUM_WORDS[mm.group(1)] + v
                break
            if re.search(r"\b" + w + r"\b", tt):
                day = v
                break
    for i, wd in enumerate(WEEKDAYS):
        if re.search(r"\b" + wd + r"\b", t):
            if re.search(r"\bnext\s+" + wd, t) and rules.get("next_weekday", "following_week") == "following_week":
                return weekday_in_week(today, i, "next")
            if re.search(r"\bthis\s+" + wd, t):
                return weekday_in_week(today, i, "this")
            if day is not None:
                break  # "Monday the 26th" -> use the day number below
            return upcoming_weekday(today, i, include_today=False)
    if day is not None:
        y = today.year
        mth = month or today.month
        try:
            d = datetime.date(y, mth, day)
        except ValueError:
            return None
        if month is None and d < today:
            mth = mth % 12 + 1
            y = y + (1 if mth == 1 else 0)
            try:
                d = datetime.date(y, mth, day)
            except ValueError:
                return None
        elif d < today - datetime.timedelta(days=180):
            d = datetime.date(y + 1, mth, day)
        return d
    return None


def parse_birth_date(text, order="dmy"):
    """Spoken or numeric birth date -> 'YYYY-MM-DD' or ''. Numeric-only dates use `order`."""
    t = str(text or "").lower().replace(",", " ")
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        return "%04d-%02d-%02d" % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    month = None
    for i, mn in enumerate(MONTHS):
        if re.search(r"\b" + mn[:3] + r"[a-z]*\b", t):
            month = i + 1
    year = None
    m = re.search(r"\b(19\d\d|20\d\d)\b", t)
    if m:
        year = int(m.group(1))
    else:
        m = re.search(r"\b(nineteen|twenty)\s+([a-z]+(?:\s+[a-z]+)?)", t.replace("-", " "))
        if m:
            rest = words_to_number(m.group(2))
            if rest is not None:
                year = (1900 if m.group(1) == "nineteen" else 2000) + int(rest)
    if month:
        tt = re.sub(r"\b(19\d\d|20\d\d)\b", " ", t)
        m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\b", tt)
        day = int(m.group(1)) if m else None
        if day is None:
            tt = tt.replace("-", " ")
            for w, v in sorted(ORD_WORDS.items(), key=lambda kv: -len(kv[0])):
                mm = re.search(r"\b(twenty|thirty)\s+" + w + r"\b", tt)
                if mm:
                    day = NUM_WORDS[mm.group(1)] + v; break
                if re.search(r"\b" + w + r"\b", tt):
                    day = v; break
        if day and year:
            return "%04d-%02d-%02d" % (year, month, day)
        return ""
    nums = re.findall(r"\d+", t)
    if len(nums) >= 3:
        a, b, c = int(nums[0]), int(nums[1]), int(nums[2])
        if len(nums[0]) == 4:
            return "%04d-%02d-%02d" % (a, b, c)
        if c < 100:
            c += 1900 if c > 30 else 2000
        d, mth = (a, b) if order == "dmy" else (b, a)
        if 1 <= mth <= 12 and 1 <= d <= 31:
            return "%04d-%02d-%02d" % (c, mth, d)
    return ""


def digits_only(text):
    t = str(text or "")
    if re.search(r"[a-z]", t.lower()):
        n = words_to_number(t)
        if n is not None:
            return str(int(n))
    return re.sub(r"\D", "", t)


def speak_date(d):
    return d.strftime("%A ") + str(d.day) + d.strftime(" %B")


def speak_amount(x):
    x = round(float(x), 2)
    return ("%d" % x) if x == int(x) else ("%.2f" % x)


def calendar_text(today, days=21):
    rows = []
    for i in range(days):
        d = today + datetime.timedelta(days=i)
        tag = "business day" if is_business_day(d) else ("holiday" if iso(d) in P["holidays"] else "weekend")
        rows.append(iso(d) + " " + d.strftime("%A") + " (" + tag + ")")
    return "\n".join(rows)


def dumps(x):
    return json.dumps(x, ensure_ascii=False)
