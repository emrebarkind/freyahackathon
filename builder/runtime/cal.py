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
    if kind == "end_of_week":           # last business day of the current week (next week's if today is it)
        d = last_business_day_of_week(today, 0)
        return d if d is not None and d >= today else last_business_day_of_week(today, 1)
    if kind == "end_of_next_week":
        return last_business_day_of_week(today, 1)
    if kind == "day_of_next_month":     # the n-th calendar day of next month
        first = end_of_month(today) + datetime.timedelta(days=1)
        return first.replace(day=min(max(n, 1), 28))
    if kind == "business_days_after_or_end_of_month":   # whichever comes first
        return min(add_business_days(today, n), end_of_month(today))
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


HOUR_WORDS = dict(one=1, two=2, three=3, four=4, five=5, six=6, seven=7, eight=8, nine=9, ten=10, eleven=11, twelve=12)
MIN_WORDS = dict(oclock=0, fifteen=15, thirty=30, fortyfive=45, five=5, ten=10, twenty=20, twentyfive=25, fifty=50)


def spoken_time(text):
    """Last time of day mentioned -> 'HH:MM' or None. Handles 11:30, 3pm, 3 o'clock, eleven in the morning,
    half past two, quarter to five, noon. Hours 1-7 without am/pm are read as afternoon (business hours)."""
    t = str(text or "").lower().replace("-", " ").replace("o'clock", "oclock").replace("o clock", "oclock")
    t = re.sub(r"forty five", "fortyfive", t)
    t = re.sub(r"twenty five", "twentyfive", t)
    cands = []
    W = "|".join(HOUR_WORDS)
    for m in re.finditer(r"\b(noon|midday)\b", t):
        cands.append((m.start(), 12, 0, "pm"))
    for m in re.finditer(r"\b(\d{1,2})[:.](\d{2})\s*(am|pm|a\.m\.|p\.m\.)?", t):
        cands.append((m.start(), int(m.group(1)), int(m.group(2)), m.group(3) or ""))
    for m in re.finditer(r"\b(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.|oclock)\b", t):
        cands.append((m.start(), int(m.group(1)), 0, m.group(2)))
    for m in re.finditer(r"\b(?:at|around|about|after|by|before|from|until|till)\s+(\d{1,2})\b(?!\s*(?:st|nd|rd|th|dollars?|days?|weeks?|[:.]\d))", t):
        cands.append((m.start(1), int(m.group(1)), 0, ""))
    for m in re.finditer(r"\b(half|quarter)\s+(past|to)\s+(" + W + r"|\d{1,2})\b", t):
        h = HOUR_WORDS.get(m.group(3)) or int(m.group(3))
        mi = 30 if m.group(1) == "half" else 15
        if m.group(2) == "to":
            h, mi = h - 1, 60 - mi
        cands.append((m.start(), h, mi, ""))
    for m in re.finditer(r"\b(" + W + r")(?:\s+(oclock|fifteen|thirty|fortyfive|twentyfive|twenty|fifty|oh five|five))?\b", t):
        before = t[max(0, m.start() - 12):m.start()]
        after = t[m.end():m.end() + 12]
        if re.search(r"(past|to)\s*$", before) or re.search(r"^\s*(of|th|st|nd|rd|days?|weeks?|months?|years?|dollars?|hundred|thousand)\b", after):
            continue
        timeish = m.group(2) or re.search(r"(at|around|about|by|after|before|from|until|till)\s*$", before) or \
            re.search(r"^\s*(in the|this|tonight|am|pm|a\.m|p\.m)", after)
        if not timeish:
            continue
        mi = MIN_WORDS.get((m.group(2) or "oclock").replace(" ", ""), 5 if m.group(2) == "oh five" else 0)
        cands.append((m.start(), HOUR_WORDS[m.group(1)], mi, ""))
    if not cands:
        return None
    pos, h, mi, ap = sorted(cands)[-1]
    tail = t[pos:pos + 40]
    if ap.startswith("p") and h < 12:
        h += 12
    elif ap.startswith("a") and h == 12:
        h = 0
    elif not ap:
        if re.search(r"afternoon|evening|tonight", tail) and h < 12:
            h += 12
        elif not re.search(r"morning", tail) and 1 <= h <= 7:
            h += 12
    if h > 23 or mi > 59:
        return None
    return "%02d:%02d" % (h, mi)


CORRECTION = re.compile(r"\b(sorry|i mean|i meant|actually|make that|no wait|wait no|rather|correction|let me correct)\b[,.]?", re.I)


def after_correction(text):
    """'the 21st, sorry, I mean the 20th' -> 'the 20th' (the part after the last correction marker)."""
    t = str(text or "")
    parts = CORRECTION.split(t)
    if len(parts) > 1:
        tail = parts[-1].strip(" ,.")
        if re.search(r"\d|[a-z]", tail, re.I):
            return tail
    return t


def parse_spoken_date(text, today, rules=None):
    corrected = after_correction(text)
    if corrected != str(text or ""):
        d = _parse_spoken_date(corrected, today, rules)
        if d is not None:
            return d
    return _parse_spoken_date(text, today, rules)


SMALL_N = dict(a=1, an=1, one=1, two=2, three=3, four=4, five=5, six=6, seven=7, eight=8, nine=9, ten=10, couple=2)
MONTH_RE = r"\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b"


def _parse_spoken_date(text, today, rules=None):
    """Best-effort spoken payment date -> datetime.date or None (relative to `today`, never the real clock).
    Handles ISO, today/tomorrow/day after tomorrow, 'in 3 days', 'a week from today', '(this|next) <weekday>',
    '<weekday> next week', 'the <weekday> after next', bare weekday (next occurrence), '<day> <month>',
    '<month> <day>', 'the 23rd', ordinal words. Negated mentions ('not today') are ignored."""
    rules = rules or {}
    t = " " + str(text or "").lower().replace("-", " ").replace(",", " ") + " "
    m = re.search(r"(\d{4}) (\d{2}) (\d{2})", t) or re.search(r"(\d{4})/(\d{2})/(\d{2})", t)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    t = re.sub(r"\b(not|can't|cannot|can not|won't|wont|couldn't)\s+(?:pay\s+|do\s+it\s+|make\s+it\s+)?(today|tomorrow|now|right now|this week)\b", " ", t)
    # relative offsets
    m = re.search(r"\b(?:in|within)\s+(a|an|one|two|three|four|five|six|seven|eight|nine|ten|couple of|\d+)\s+(day|days|week|weeks)\b", t) or \
        re.search(r"\b(a|an|one|two|three|four|five|six|seven|\d+)\s+(day|days|week|weeks)\s+from\s+(?:today|now)\b", t)
    if m:
        n = m.group(1).replace(" of", "")
        n = int(n) if n.isdigit() else SMALL_N.get(n, 1)
        return today + datetime.timedelta(days=n * (7 if m.group(2).startswith("week") else 1))
    if re.search(r"\bday after tomorrow\b", t):
        return today + datetime.timedelta(days=2)
    month = None
    for mm in re.finditer(MONTH_RE, t):
        w = mm.group(1)
        if w == "may":   # 'may' is a month only next to a day number / ordinal
            ctx = t[max(0, mm.start() - 15):mm.end() + 15]
            if not re.search(r"\d|\b(first|second|third|[a-z]+th|twenty|thirty)\b", ctx):
                continue
        month = [i for i, mn in enumerate(MONTHS) if mn.startswith(w[:3])][0] + 1
    day = None
    for mm in re.finditer(r"\b(\d{1,2})(?:st|nd|rd|th)?\b(?!\s*(?::|am|pm|a\.m|p\.m|o'clock|oclock|dollars?|euros?|pounds?|days?|weeks?|hundred))", t):
        before = t[max(0, mm.start() - 8):mm.start()]
        if re.search(r"\b(at|around|about|after|before|by)\s+$", before) and not month:
            continue
        if 1 <= int(mm.group(1)) <= 31:
            day = int(mm.group(1))
    if day is None:
        for w, v in sorted(ORD_WORDS.items(), key=lambda kv: -len(kv[0])):
            mm = re.search(r"\b(twenty|thirty)\s+" + w + r"\b", t)
            if mm:
                day = NUM_WORDS[mm.group(1)] + v
                break
            if re.search(r"\b" + w + r"\b", t) and not re.search(r"\b" + w + r"\s+(week|time|attempt)", t):
                day = v
                break
    if day is None and month:
        toks = [x for x in t.split() if x]
        d0, _ = spoken_day([x for x in toks if not re.fullmatch(MONTH_RE.strip("\\b"), x)])
        if d0:
            day = d0
    nxt = rules.get("next_weekday", "following_week")
    for i, wd in enumerate(WEEKDAYS):
        if re.search(r"\b" + wd + r"s?\b", t):
            if re.search(r"\b" + wd + r"\s+after\s+next\b", t):
                return weekday_in_week(today, i, "this") + datetime.timedelta(weeks=2)
            if re.search(r"\b(" + wd + r"\s+next\s+week|next\s+week\s+(on\s+)?" + wd + r"|a\s+week\s+on\s+" + wd + r"|" + wd + r"\s+week)\b", t):
                return weekday_in_week(today, i, "next")
            if re.search(r"\bnext\s+" + wd, t):
                return weekday_in_week(today, i, "next") if nxt == "following_week" else upcoming_weekday(today, i)
            if re.search(r"\bthis\s+(coming\s+)?" + wd, t):
                d = weekday_in_week(today, i, "this")
                return d if d >= today else upcoming_weekday(today, i)
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
    if re.search(r"\btomorrow\b", t):
        return today + datetime.timedelta(days=1)
    if re.search(r"\b(today|now|right away|immediately|this afternoon|this evening|tonight)\b", t):
        return today
    return None


def _tokens(text):
    t = str(text or "").lower()
    t = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", t)
    t = re.sub(r"[-,./]", " ", t)
    return [w for w in t.split() if w not in ("the", "of", "and", "a", "um", "uh", "er", "its", "it's", "is", "my")]


UNITS = dict(zero=0, oh=0, o=0, one=1, two=2, three=3, four=4, five=5, six=6, seven=7, eight=8, nine=9)
TEENS = dict(ten=10, eleven=11, twelve=12, thirteen=13, fourteen=14, fifteen=15, sixteen=16, seventeen=17,
             eighteen=18, nineteen=19)
TENS = dict(twenty=20, thirty=30, forty=40, fifty=50, sixty=60, seventy=70, eighty=80, ninety=90)


def digit_groups(tokens):
    """Spoken digit string -> digits, keeping leading zeros: 'oh three five eight' -> '0358',
    'forty four seventy one' -> '4471', 'double seven two one' -> '7721'."""
    out, i = "", 0
    while i < len(tokens):
        w = tokens[i]
        if re.fullmatch(r"\d+", w):
            out += w
        elif w in ("double", "triple") and i + 1 < len(tokens) and tokens[i + 1] in UNITS:
            out += str(UNITS[tokens[i + 1]]) * (2 if w == "double" else 3)
            i += 1
        elif w in UNITS:
            out += str(UNITS[w])
        elif w in TEENS:
            out += str(TEENS[w])
        elif w in TENS:
            if i + 1 < len(tokens) and tokens[i + 1] in UNITS and UNITS[tokens[i + 1]] > 0 and tokens[i + 1] not in ("oh", "o"):
                out += str(TENS[w] + UNITS[tokens[i + 1]])
                i += 1
            else:
                out += str(TENS[w])
        elif w == "hundred" and out:
            out += "00"
        i += 1
    return out


def cardinal(tokens):
    """'four thousand four hundred seventy one' -> 4471 ; None if no number words."""
    total, cur, seen = 0, 0, False
    for w in tokens:
        if re.fullmatch(r"\d+", w):
            cur += int(w); seen = True
        elif w in UNITS:
            cur += UNITS[w]; seen = True
        elif w in TEENS:
            cur += TEENS[w]; seen = True
        elif w in TENS:
            cur += TENS[w]; seen = True
        elif w == "hundred":
            cur = (cur or 1) * 100; seen = True
        elif w == "thousand":
            total += (cur or 1) * 1000; cur = 0; seen = True
    return total + cur if seen else None


def digits_only(text):
    toks = _tokens(text)
    if any(w in ("hundred", "thousand") for w in toks):
        n = cardinal(toks)
        return str(n) if n is not None else ""
    return digit_groups(toks)


def spoken_year(tokens):
    """Year from the tokens left after month/day are removed."""
    for w in tokens:
        if re.fullmatch(r"(19|20)\d\d", w):
            return int(w)
    toks = [w for w in tokens if w in UNITS or w in TEENS or w in TENS or w in ("hundred", "thousand") or re.fullmatch(r"\d{1,2}", w)]
    if not toks:
        return None
    if "thousand" in toks:
        n = cardinal(toks)
        return n if n and 1900 <= n <= 2100 else None
    if toks[0] in ("nineteen", "twenty") and len(toks) >= 2:
        rest = digit_groups(toks[1:])
        if rest.isdigit() and len(rest) <= 2:
            return (1900 if toks[0] == "nineteen" else 2000) + int(rest)
    g = digit_groups(toks)
    if len(g) == 4 and g[:2] in ("19", "20"):
        return int(g)
    if len(g) == 2:
        y = int(g)
        return 1900 + y if y > 30 else 2000 + y
    return None


def spoken_day(tokens):
    """(day, tokens_without_day)"""
    for i, w in enumerate(tokens):
        if w in ("twenty", "thirty") and i + 1 < len(tokens) and tokens[i + 1] in ORD_WORDS and ORD_WORDS[tokens[i + 1]] < 10:
            return TENS[w] + ORD_WORDS[tokens[i + 1]], tokens[:i] + tokens[i + 2:]
    for i, w in enumerate(tokens):
        if w in ORD_WORDS:
            return ORD_WORDS[w], tokens[:i] + tokens[i + 1:]
    for i, w in enumerate(tokens):
        if re.fullmatch(r"\d{1,2}", w) and 1 <= int(w) <= 31:
            return int(w), tokens[:i] + tokens[i + 1:]
    for i, w in enumerate(tokens):   # "January eight 1991", "twenty-one August", "thirty January"
        if w in ("twenty", "thirty"):
            nx = tokens[i + 1] if i + 1 < len(tokens) else ""
            if nx in UNITS and UNITS[nx] > 0 and nx not in ("oh", "o") and TENS[w] + UNITS[nx] <= 31:
                return TENS[w] + UNITS[nx], tokens[:i] + tokens[i + 2:]
            return TENS[w], tokens[:i] + tokens[i + 1:]
        if w in UNITS and UNITS[w] > 0:
            return UNITS[w], tokens[:i] + tokens[i + 1:]
        if w in TEENS and i + 1 < len(tokens) and tokens[i + 1] in TENS:
            continue
        if w in TEENS:
            return TEENS[w], tokens[:i] + tokens[i + 1:]
    return None, tokens


def parse_birth_date(text, order="dmy"):
    """Spoken or numeric birth date -> 'YYYY-MM-DD' or ''. Numeric-only dates use `order` (dmy or mdy)."""
    raw = str(text or "").lower()
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", raw)
    if m:
        return "%04d-%02d-%02d" % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    toks = _tokens(raw)
    month, mi = None, None
    for i, w in enumerate(toks):
        for j, mn in enumerate(MONTHS):
            if len(w) >= 3 and mn.startswith(w[:3]) and (w == mn or w == mn[:3] or w == mn[:4] or mn.startswith(w)):
                month, mi = j + 1, i
                break
        if month:
            break
    if month:
        rest = toks[:mi] + toks[mi + 1:]
        # a 4-digit year or a spoken year usually comes after the day; take the day first
        year_tok = [w for w in rest if re.fullmatch(r"(19|20)\d\d", w)]
        if year_tok:
            rest2 = [w for w in rest if w != year_tok[0]]
            day, _ = spoken_day(rest2)
            year = int(year_tok[0])
        else:
            day, left = spoken_day(rest)
            year = spoken_year(left)
        if day and year and 1 <= day <= 31:
            return "%04d-%02d-%02d" % (year, month, day)
        return ""
    nums = re.findall(r"\d+", raw)
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
