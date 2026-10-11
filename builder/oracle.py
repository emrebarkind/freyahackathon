"""An independent reading of the materials, run next to the spec reading: it never sees the spec. It writes
behaviour checks (the frozen-key format of eval/packages/CHECKS.md) for the rules most likely to be misread, with
the expected value computed from the materials only. The engine then answers the same checks from the spec
(eval/score.py, the scorer used for every eval package), and every disagreement is either fixed by one targeted
repair or reported as uncertain. A disagreement never silently changes the spec: the materials decide.

Measured before it was built: on the two hardest first attempts, independent readings of this kind flagged 7 of 7
real failures with no false flag (f1 first attempt 4/4, h2 retest 3/3 including a rule the build had missed).
"""
import copy
import datetime
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
TYPES = ["deadline", "floor", "attempts", "offers", "business_day", "callback_ok", "close", "note", "transfer",
         "identity_fields", "identity_max_wrong", "id_answer", "promise_amount"]
SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["checks"],
    "properties": {"checks": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["id", "type", "input", "expect", "source"],
        "properties": {"id": {"type": "string"}, "type": {"type": "string", "enum": TYPES},
                       "input": {"type": "object"}, "expect": {}, "source": {"type": "string"}}}}}}

INSTRUCTIONS = """You are an independent auditor. You will NOT see how anyone else read these materials. Write behaviour
checks that a correct phone agent built from these materials must pass, in the format described below, for the rules
most likely to be misread. Compute every expected value yourself, strictly from the materials: apply their stated order
of precedence (a later memo or amendment beats the rule it changes) and any dated change only from its date.

Cover, where the materials decide them:
- deadlines on boundary days for every band (the day before, the day of and the day after a rollover or month end,
  a holiday or weekend move, the first and last days_late of a band);
- floors with their rounding and minimums, for every product type;
- offers (and attempts) after a flatly refused opening ask, especially where the materials say whether the opening
  ask counts, whether a skipped repeated step counts, and what the limit is; include a call on a deadline day;
- codes: close / note / transfer for each situation the materials decide, and for a dated code change the day
  before, the day of and the day after (put "now": "YYYY-MM-DDT11:00" in the input of those checks);
- identity fields, the wrong-answer limit, the answer format; the promise amount unit.
Write 14 to 22 checks. Use call dates from October 2026 to January 2027, on business days unless the check is about a
non-business day. Product records in inputs must have exactly the fields the tool API's get_account product record
has (use its field names and its product type values). Do not invent rules the materials do not state; skip a type
the materials do not decide. "source" quotes the deciding sentence(s) word for word.

The check format:
{checks}

A calendar to read weekdays from (no bank holidays marked; take holidays from the materials):
{calendar}
"""


def calendar_text(start=datetime.date(2026, 10, 1), end=datetime.date(2027, 1, 31)):
    rows, d = [], start
    while d <= end:
        rows.append(f"{d.isoformat()} {d.strftime('%a')}")
        d += datetime.timedelta(days=1)
    return ", ".join(rows)


def prompt(base_materials):
    checks = (ROOT / "eval" / "packages" / "CHECKS.md").read_text()
    return base_materials + "\n\n" + INSTRUCTIONS.format(checks=checks, calendar=calendar_text())


def _scorer():
    spec_ = importlib.util.spec_from_file_location("builder_oracle_score", ROOT / "eval" / "score.py")
    mod = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(mod)
    return mod


def compare(spec, openapi, checks):
    """(disagreements, unusable) between the engine's answers and the independent reading's expected values.
    A check the engine cannot even evaluate (wrong input shape) is unusable, not a disagreement."""
    score = _scorer()
    score.OPENAPI[0] = openapi
    s = score.setup(spec, openapi)
    dis, unusable = [], []
    for c in checks or []:
        if not isinstance(c, dict) or c.get("type") not in TYPES:
            continue
        c = copy.deepcopy(c)
        try:
            got = score.answer(s, c)
        except Exception as e:
            unusable.append(dict(id=c.get("id"), error=f"{type(e).__name__}: {str(e)[:120]}"))
            continue
        if isinstance(got, str) and got.startswith("ERROR"):
            unusable.append(dict(id=c.get("id"), error=got[:120]))
            continue
        if not score.same(got, c.get("expect")):
            dis.append(dict(id=c.get("id"), type=c["type"], input=c.get("input"), expect=c.get("expect"),
                            got=got, source=c.get("source", "")))
    return dis, unusable


REPAIR = """An independent reading of the materials (it did not see your spec) expects different behaviour from the
agent your spec produces in these checks:
{dis}
Either side may be wrong: the independent reading can misread a rule or miscount weekdays. For each check, find the
sentences in the materials that decide it (precedence and dated changes apply). If the materials decide what the
independent reading expects and your spec does otherwise, correct the spec. If the materials decide what your spec
does, keep it. If the spec format cannot express the rule, add it, quoted, to "unsupported_rules" (a list).
Answer with "changes" (dotted path -> new value, e.g. "bands.1.deadline": {{...}}; list items by index; use {{}} for no
change) and "verdicts" (check id -> "spec_right" | "spec_wrong" | "unsupported")."""

PATCH_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["changes", "verdicts"],
                "properties": {"changes": {"type": "object"},
                               "verdicts": {"type": "object", "additionalProperties": {"type": "string"}}}}
